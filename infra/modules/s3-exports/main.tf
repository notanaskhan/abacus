# Engagement export bundles (A-01-T18/T19, DEC-433; DEC-454). The export workflow on the worker
# writes sealed 64 MiB segments under exports/<tenant>/<export_id>/ and deletes a rebuilt tail; the
# API streams them back for the download (A-01-T22, ADR-104: no presigned link). A bundle is a
# transient copy (P-14), so: no Object Lock, and every object is gone within 7 days (current
# versions expire after var.expiry_days = 6, the noncurrent copy 1 day later).
# Each segment is already sealed under the tenant's key by the app (kernel.crypto.seal); the
# bucket's own SSE-KMS key is the platform layer underneath it.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  bucket_name  = "abacus-${var.environment}-exports"
  account_root = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  # Keys only through S3, in this region, for this bucket (with bucket keys the encryption
  # context is the bucket's ARN).
  via_s3  = "s3.${data.aws_region.current.region}.amazonaws.com"
  prefix  = "exports/"
  account = data.aws_caller_identity.current.account_id
  # The task roles that may use the key, by name (Q-01-T15 creates them); none until named.
  key_users = [
    for name in compact([var.worker_task_role_name, var.api_task_role_name]) :
    "arn:aws:iam::${local.account}:role/${name}"
  ]
}

# --- encryption ---------------------------------------------------------------------------------

data "aws_iam_policy_document" "key" {
  # The account administers the key but cannot use it: no Encrypt, Decrypt or GenerateDataKey
  # here, so an IAM policy alone never reaches the data (security review, DEC-454).
  statement {
    sid = "KeyAdministration"
    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Get*",
      "kms:Delete*",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
      "kms:RotateKeyOnDemand",
    ]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = [local.account_root]
    }
  }

  # Use, only by the named task roles, only through S3 in this region, only for this bucket.
  dynamic "statement" {
    for_each = length(local.key_users) > 0 ? [1] : []

    content {
      sid       = "TaskRolesUseThroughS3"
      actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*"]
      resources = ["*"]

      principals {
        type        = "AWS"
        identifiers = local.key_users
      }

      condition {
        test     = "StringEquals"
        variable = "kms:ViaService"
        values   = [local.via_s3]
      }

      condition {
        test     = "StringEquals"
        variable = "kms:EncryptionContext:aws:s3:arn"
        values   = ["arn:aws:s3:::${local.bucket_name}"]
      }
    }
  }
}

resource "aws_kms_key" "exports" {
  description             = "Encrypts engagement export segments in ${local.bucket_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "exports" {
  name          = "alias/${local.bucket_name}"
  target_key_id = aws_kms_key.exports.key_id
}

# --- bucket -------------------------------------------------------------------------------------

resource "aws_s3_bucket" "exports" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_ownership_controls" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "exports" {
  bucket = aws_s3_bucket.exports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioned like every bucket here (infra/tests): a rebuild overwrites a segment, and the
# lifecycle below removes the noncurrent copy a day later.
resource "aws_s3_bucket_versioning" "exports" {
  bucket = aws_s3_bucket.exports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.exports.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    id     = "expire-exports"
    status = "Enabled"

    filter {}

    expiration {
      days = var.expiry_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "remove-expired-delete-markers"
    status = "Enabled"

    filter {}

    expiration {
      expired_object_delete_marker = true
    }
  }

  depends_on = [aws_s3_bucket_versioning.exports]
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "DenyPlainHttp"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.exports.arn, "${aws_s3_bucket.exports.arn}/*"]

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

  # Every object is under this bucket's key: a put naming another key, or another kind of
  # encryption, is refused. A put naming none takes the default (this key) from the bucket.
  statement {
    sid       = "DenyOtherKeys"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.exports.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "StringNotEqualsIfExists"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = [aws_kms_key.exports.arn]
    }
  }

  statement {
    sid       = "DenyOtherEncryption"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.exports.arn}/*"]

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

  # A transient bucket never takes Object Lock or a public grant, whoever asks.
  statement {
    sid       = "DenyObjectLockAndAcls"
    effect    = "Deny"
    actions   = ["s3:PutBucketObjectLockConfiguration", "s3:PutObjectRetention", "s3:PutObjectLegalHold", "s3:PutBucketAcl", "s3:PutObjectAcl"]
    resources = [aws_s3_bucket.exports.arn, "${aws_s3_bucket.exports.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "exports" {
  bucket = aws_s3_bucket.exports.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [aws_s3_bucket_public_access_block.exports]
}

# --- task-role policies -------------------------------------------------------------------------

# The worker builds exports: writes segments, reads them back, lists and deletes a rebuilt tail
# (export_storage.put_segments, _drop_from).
data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "ListExportPrefixes"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.exports.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.prefix}*"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account]
    }
  }

  statement {
    sid       = "WriteExportSegments"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.exports.arn}/${local.prefix}*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account]
    }
  }

  statement {
    sid       = "UseExportsKeyThroughS3"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [aws_kms_key.exports.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = [local.via_s3]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:aws:s3:arn"
      values   = [aws_s3_bucket.exports.arn]
    }
  }
}

# The API only streams a ready export back (A-01-T22): read, never write, list or delete.
data "aws_iam_policy_document" "api" {
  statement {
    sid       = "ReadExportSegments"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.exports.arn}/${local.prefix}*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account]
    }
  }

  statement {
    sid       = "DecryptExportsKeyThroughS3"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.exports.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = [local.via_s3]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:aws:s3:arn"
      values   = [aws_s3_bucket.exports.arn]
    }
  }
}

resource "aws_iam_policy" "worker" {
  name        = "${local.bucket_name}-worker"
  description = "Worker task role: build, read back and prune engagement export segments."
  policy      = data.aws_iam_policy_document.worker.json
}

resource "aws_iam_policy" "api" {
  name        = "${local.bucket_name}-api"
  description = "API task role: read engagement export segments for the download."
  policy      = data.aws_iam_policy_document.api.json
}

resource "aws_iam_role_policy_attachment" "worker" {
  count = var.worker_task_role_name == null ? 0 : 1

  role       = var.worker_task_role_name
  policy_arn = aws_iam_policy.worker.arn
}

resource "aws_iam_role_policy_attachment" "api" {
  count = var.api_task_role_name == null ? 0 : 1

  role       = var.api_task_role_name
  policy_arn = aws_iam_policy.api.arn
}
