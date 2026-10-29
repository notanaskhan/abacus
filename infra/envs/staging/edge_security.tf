# Q-01-T15: the firm edge's WAF (rules 1-7, managed rules in count mode for the first weeks,
# chapter 06 §1.13) with its logs in S3, `authorization` and `cookie` redacted (modules/waf). The
# org's region guard keeps CloudWatch Logs out of us-east-1, so WebACL logs go to an
# `aws-waf-logs-` bucket in us-east-2, written by the log delivery service under its own key.

data "aws_iam_policy_document" "waf_logs_key" {
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account}:root"]
    }
  }

  statement {
    sid       = "LogDelivery"
    actions   = ["kms:GenerateDataKey*", "kms:Decrypt"]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }
}

resource "aws_kms_key" "waf_logs" {
  count                   = local.enabled ? 1 : 0
  description             = "Encrypts the staging firm WAF logs"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.waf_logs_key.json
}

resource "aws_s3_bucket" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = "aws-waf-logs-abacus-staging-firm"
}

resource "aws_s3_bucket_ownership_controls" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.waf_logs[0].arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id

  rule {
    id     = "expire-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.waf_logs]
}

data "aws_iam_policy_document" "waf_logs_bucket" {
  count = local.enabled ? 1 : 0

  statement {
    sid       = "DenyPlainHttp"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.waf_logs[0].arn, "${aws_s3_bucket.waf_logs[0].arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid       = "LogDeliveryWrite"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.waf_logs[0].arn}/AWSLogs/${local.account}/*"]

    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }

  statement {
    sid       = "LogDeliveryAcl"
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.waf_logs[0].arn]

    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }
}

resource "aws_s3_bucket_policy" "waf_logs" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id
  policy = data.aws_iam_policy_document.waf_logs_bucket[0].json

  depends_on = [aws_s3_bucket_public_access_block.waf_logs]
}

module "firm_waf" {
  source = "../../modules/waf"
  count  = local.enabled ? 1 : 0

  name                 = "abacus-staging-firm"
  managed_rules_action = var.firm_managed_rules_action
  log_destination_arn  = aws_s3_bucket.waf_logs[0].arn
}

# The firm certificate (us-east-1, DNS-validated) once the domain exists; the record goes in the
# shared account's zone (Q-01-T07), so validation is the builder's step until both exist.
resource "aws_acm_certificate" "firm" {
  count             = var.firm_host == null ? 0 : 1
  region            = "us-east-1"
  domain_name       = var.firm_host
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# The synthetic canary firm's tenant key, declared here rather than made by the keyops worker
# (Q-01-T15): the canary must not depend on the workflow it checks. Tagged like the worker's keys.
resource "aws_kms_key" "canary_tenant" {
  count                   = var.canary_tenant_id == null ? 0 : 1
  description             = "abacus staging tenant key (synthetic canary)"
  multi_region            = true
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags = {
    "abacus:env"    = "staging"
    "abacus:tenant" = var.canary_tenant_id
  }
}

resource "aws_kms_alias" "canary_tenant" {
  count         = var.canary_tenant_id == null ? 0 : 1
  name          = "alias/abacus/tenant/${var.canary_tenant_id}"
  target_key_id = aws_kms_key.canary_tenant[0].key_id
}
