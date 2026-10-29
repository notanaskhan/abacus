# Q-01-T07 (ADR-088; SPEC-050 AC-19): the release registry. The backend image goes to one ECR
# repository (immutable tags, scan on push) and every release record and SPA bundle to
# abacus-shared-artifacts; build.yml writes both through the main-only build role. Environment
# accounts read them: their account IDs come from the untracked terraform.tfvars, so a root
# without them grants no cross-account read. Deferred to later passes (DEC-1003): ECR replication
# to production and us-west-2, Route 53 zones (no domain yet), the design-baselines bucket and the
# weekly git bundle backup.

data "aws_caller_identity" "current" {}

locals {
  account_root = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  oidc_host    = "token.actions.githubusercontent.com"
  oidc_arn     = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.oidc_host}"
  readers      = [for id in var.reader_account_ids : "arn:aws:iam::${id}:root"]
}

# --- image repository ---------------------------------------------------------------------------

resource "aws_ecr_repository" "backend" {
  name                 = "abacus-backend"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.artifacts.arn
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Untagged layers go after 7 days; tagged release images are kept."
      selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 7 }
      action       = { type = "expire" }
    }]
  })
}

data "aws_iam_policy_document" "ecr_readers" {
  count = length(local.readers) > 0 ? 1 : 0

  statement {
    sid     = "EnvironmentPull"
    actions = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]

    principals {
      type        = "AWS"
      identifiers = local.readers
    }
  }
}

resource "aws_ecr_repository_policy" "backend" {
  count      = length(local.readers) > 0 ? 1 : 0
  repository = aws_ecr_repository.backend.name
  policy     = data.aws_iam_policy_document.ecr_readers[0].json
}

# --- encryption ---------------------------------------------------------------------------------

data "aws_iam_policy_document" "artifacts_key" {
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
    for_each = length(local.readers) > 0 ? [1] : []
    content {
      sid       = "EnvironmentDecrypt"
      actions   = ["kms:Decrypt", "kms:DescribeKey"]
      resources = ["*"]

      principals {
        type        = "AWS"
        identifiers = local.readers
      }
    }
  }
}

resource "aws_kms_key" "artifacts" {
  description             = "Encrypts abacus release images and abacus-shared-artifacts"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.artifacts_key.json
}

resource "aws_kms_alias" "artifacts" {
  name          = "alias/abacus-shared-artifacts"
  target_key_id = aws_kms_key.artifacts.key_id
}

# --- artifacts bucket ---------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  bucket = "abacus-shared-artifacts"
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.artifacts.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "noncurrent-and-uploads"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.artifacts]
}

data "aws_iam_policy_document" "artifacts_bucket" {
  statement {
    sid       = "DenyPlainHttp"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]

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
    for_each = length(local.readers) > 0 ? [1] : []
    content {
      sid       = "EnvironmentRead"
      actions   = ["s3:GetObject", "s3:ListBucket"]
      resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]

      principals {
        type        = "AWS"
        identifiers = local.readers
      }
    }
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = data.aws_iam_policy_document.artifacts_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}

# --- CI build role (main only) ------------------------------------------------------------------

data "aws_iam_policy_document" "build_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

data "aws_iam_policy_document" "build" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
      "ecr:DescribeImages", "ecr:DescribeImageScanFindings", "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.backend.arn]
  }

  statement {
    sid       = "InspectorFindings"
    actions   = ["inspector2:ListFindings", "inspector2:ListCoverage"]
    resources = ["*"]
  }

  statement {
    sid       = "ArtifactsList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]
  }

  statement {
    sid       = "ArtifactsWrite"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/releases/*", "${aws_s3_bucket.artifacts.arn}/web/*"]
  }

  statement {
    sid       = "ArtifactsKey"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [aws_kms_key.artifacts.arn]
  }
}

resource "aws_iam_role" "build" {
  name                 = "abacus-ci-build"
  description          = "build.yml: pushes the backend image and writes release records; GitHub OIDC, main only."
  assume_role_policy   = data.aws_iam_policy_document.build_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "build" {
  name   = "release-artifacts"
  role   = aws_iam_role.build.name
  policy = data.aws_iam_policy_document.build.json
}
