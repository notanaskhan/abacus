# A private bucket with its own KMS key (Q-01-T07, T14): public access blocked, versioned, SSE-KMS,
# TLS-only, owner-enforced, noncurrent versions gone after 30 days, an optional expiry. Readers and
# writers are named roles; nothing is public.

data "aws_caller_identity" "current" {}

locals {
  account_root = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  users        = distinct(concat(var.reader_role_arns, var.writer_role_arns))
}

data "aws_iam_policy_document" "key" {
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = [local.account_root]
    }
  }

  dynamic "statement" {
    for_each = length(local.users) > 0 ? [1] : []
    content {
      sid       = "RoleUse"
      actions   = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
      resources = ["*"]

      principals {
        type        = "AWS"
        identifiers = local.users
      }
    }
  }
}

resource "aws_kms_key" "this" {
  description             = "Encrypts ${var.name} (${var.purpose})"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}

resource "aws_s3_bucket" "this" {
  bucket = var.name
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "versions-and-uploads"
    status = "Enabled"

    filter {}

    dynamic "expiration" {
      for_each = var.expire_days == null ? [] : [var.expire_days]
      content {
        days = expiration.value
      }
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "DenyPlainHttp"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]

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

  dynamic "statement" {
    for_each = length(var.reader_role_arns) > 0 ? [1] : []
    content {
      sid       = "Read"
      actions   = ["s3:GetObject", "s3:ListBucket"]
      resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]

      principals {
        type        = "AWS"
        identifiers = var.reader_role_arns
      }
    }
  }

  dynamic "statement" {
    for_each = length(var.writer_role_arns) > 0 ? [1] : []
    content {
      sid       = "Write"
      actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]

      principals {
        type        = "AWS"
        identifiers = var.writer_role_arns
      }
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [aws_s3_bucket_public_access_block.this]
}
