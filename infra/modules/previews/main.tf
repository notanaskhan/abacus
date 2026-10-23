# PR preview host (Q-01-T49, D-OPS-13; chapter 06 section 2.7). A private bucket of fixture builds
# under pr-<n>/, served only through CloudFront (origin access control), gated by a CloudFront
# Function that checks a cookie against a key held in a CloudFront KeyValueStore. The key is put
# into the store by hand, so it is in neither git nor Terraform state. Objects expire after 14 days.

data "aws_caller_identity" "current" {}

locals {
  account_root = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  oidc_host    = "token.actions.githubusercontent.com"
  oidc_arn     = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.oidc_host}"
}

# --- encryption ---------------------------------------------------------------------------------

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

  # CloudFront reads SSE-KMS objects through OAC only for this distribution.
  statement {
    sid       = "CloudFrontDecrypt"
    actions   = ["kms:Decrypt"]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudfront_distribution.previews.arn]
    }
  }
}

resource "aws_kms_key" "previews" {
  description             = "Encrypts PR preview bundles in ${var.bucket_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  policy                  = data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "previews" {
  name          = "alias/${var.bucket_name}"
  target_key_id = aws_kms_key.previews.key_id
}

# --- bucket -------------------------------------------------------------------------------------

resource "aws_s3_bucket" "previews" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_ownership_controls" "previews" {
  bucket = aws_s3_bucket.previews.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "previews" {
  bucket = aws_s3_bucket.previews.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "previews" {
  bucket = aws_s3_bucket.previews.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "previews" {
  bucket = aws_s3_bucket.previews.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.previews.arn
    }
  }
}

# Closing a PR deletes its prefix; versioning keeps the deleted objects as noncurrent, so they go
# a day later. Anything still current goes after the expiry window, labelled PR or not.
resource "aws_s3_bucket_lifecycle_configuration" "previews" {
  bucket = aws_s3_bucket.previews.id

  rule {
    id     = "expire-previews"
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

  depends_on = [aws_s3_bucket_versioning.previews]
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "DenyPlainHttp"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.previews.arn, "${aws_s3_bucket.previews.arn}/*"]

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
    sid       = "CloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.previews.arn}/pr-*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudfront_distribution.previews.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "previews" {
  bucket = aws_s3_bucket.previews.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [aws_s3_bucket_public_access_block.previews]
}

# --- edge ---------------------------------------------------------------------------------------

# Holds `gate-key` only. Terraform creates the empty store; the value is put by hand.
resource "aws_cloudfront_key_value_store" "gate" {
  name    = "${var.bucket_name}-gate"
  comment = "Preview gate key; value set by hand, never in git or state"
}

resource "aws_cloudfront_function" "gate" {
  name    = "${var.bucket_name}-gate"
  runtime = "cloudfront-js-2.0"
  comment = "Cookie gate and PR routing for previews (Q-01-T49)"
  publish = true
  code    = file("${path.module}/gate.js")

  key_value_store_associations = [aws_cloudfront_key_value_store.gate.arn]
}

resource "aws_cloudfront_origin_access_control" "previews" {
  name                              = var.bucket_name
  description                       = "PR previews bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

# Static fixture bundles behind a cookie gate on the default CloudFront domain: no WAF (nothing
# dynamic to protect, and every request is refused before the cache without the cookie) and no
# access logs (no visitors but the builder). The default certificate is used until a preview
# hostname exists.
#trivy:ignore:AVD-AWS-0010
#trivy:ignore:AVD-AWS-0011
#trivy:ignore:AVD-AWS-0013
resource "aws_cloudfront_distribution" "previews" {
  enabled             = true
  comment             = "abacus PR previews (fixture builds, cookie-gated)"
  price_class         = "PriceClass_100"
  http_version        = "http2and3"
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  origin {
    origin_id                = "previews"
    domain_name              = aws_s3_bucket.previews.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.previews.id
  }

  default_cache_behavior {
    target_origin_id           = "previews"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.gate.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# --- CI role (pull requests of this repository only) -------------------------------------------

data "aws_iam_policy_document" "ci_trust" {
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
      values   = ["repo:${var.github_repo}:pull_request"]
    }
  }
}

data "aws_iam_policy_document" "ci" {
  statement {
    sid       = "ListPreviewPrefixes"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.previews.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["pr-*"]
    }
  }

  statement {
    sid       = "WritePreviewPrefixes"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.previews.arn}/pr-*"]
  }

  statement {
    sid       = "EncryptPreviewObjects"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [aws_kms_key.previews.arn]
  }
}

resource "aws_iam_role" "ci" {
  name                 = var.ci_role_name
  description          = "Uploads and deletes PR preview builds (preview.yml); GitHub OIDC, pull_request only."
  assume_role_policy   = data.aws_iam_policy_document.ci_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "ci" {
  name   = "preview-objects"
  role   = aws_iam_role.ci.name
  policy = data.aws_iam_policy_document.ci.json
}
