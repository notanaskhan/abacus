locals {
  name_prefix = "abacus-tf"

  # Environment -> account that hosts its roles. production-dr runs in the production account.
  env_accounts = merge(
    { shared = var.shared_account_id },
    var.staging_account_id == null ? {} : { staging = var.staging_account_id },
    var.production_account_id == null ? {} : {
      production    = var.production_account_id
      production-dr = var.production_account_id
    },
  )

  # Roles in other accounts that reach the state bucket and key.
  remote_env_accounts = { for env, acct in local.env_accounts : env => acct if acct != var.shared_account_id }
  remote_accounts     = toset(values(local.remote_env_accounts))
}

data "aws_iam_policy_document" "state_key" {
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.shared_account_id}:root"]
    }
  }

  dynamic "statement" {
    for_each = local.remote_accounts

    content {
      sid       = "UseFromAccount${statement.value}"
      actions   = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
      resources = ["*"]

      principals {
        type        = "AWS"
        identifiers = ["arn:aws:iam::${statement.value}:root"]
      }

      condition {
        test     = "ArnLike"
        variable = "aws:PrincipalArn"
        values   = ["arn:aws:iam::${statement.value}:role/${local.name_prefix}-*"]
      }
    }
  }
}

resource "aws_kms_key" "state" {
  description             = "Encrypts Terraform state in ${var.state_bucket_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.state_key.json
}

resource "aws_kms_alias" "state" {
  name          = "alias/abacus-terraform-state"
  target_key_id = aws_kms_key.state.key_id
}

resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 365
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.state]
}

data "aws_iam_policy_document" "state_bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]

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

  # The backend sends no encryption header (the bucket default applies); refuse any other algorithm.
  statement {
    sid       = "DenyNonKmsEncryption"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.state.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "StringNotEqualsIfExists"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }

  dynamic "statement" {
    for_each = local.remote_env_accounts

    content {
      sid       = "State${replace(title(statement.key), "-", "")}Objects"
      actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      resources = ["${aws_s3_bucket.state.arn}/envs/${statement.key}/*"]

      principals {
        type        = "AWS"
        identifiers = ["arn:aws:iam::${statement.value}:root"]
      }

      condition {
        test     = "ArnLike"
        variable = "aws:PrincipalArn"
        values = [
          "arn:aws:iam::${statement.value}:role/${local.name_prefix}-plan-${statement.key}",
          "arn:aws:iam::${statement.value}:role/${local.name_prefix}-apply-${statement.key}",
        ]
      }
    }
  }

  dynamic "statement" {
    for_each = local.remote_env_accounts

    content {
      sid       = "State${replace(title(statement.key), "-", "")}List"
      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.state.arn]

      principals {
        type        = "AWS"
        identifiers = ["arn:aws:iam::${statement.value}:root"]
      }

      condition {
        test     = "ArnLike"
        variable = "aws:PrincipalArn"
        values = [
          "arn:aws:iam::${statement.value}:role/${local.name_prefix}-plan-${statement.key}",
          "arn:aws:iam::${statement.value}:role/${local.name_prefix}-apply-${statement.key}",
        ]
      }
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}
