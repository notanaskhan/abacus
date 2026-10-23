# The client portal edge (Q-01-T56; OPS-14 part; D-OPS-10; ADR-163). One CloudFront multi-tenant
# distribution serves the portal entry (`dist/portal` from `vite build --mode portal`, P-08-T07)
# from a private bucket, and `/v1/*` same-origin from the internal API load balancer through a VPC
# origin. Hosts are distribution tenants:
# - `default`: the wildcard `*.<portal_base_domain>`, every firm's default host, on the
#   distribution's wildcard ACM certificate;
# - `canary`: one firm custom domain with its own CloudFront-managed certificate, for pen test 1.
# Further custom domains are tenants added by R-01/ADM-10 in P1, never new distributions.
# The host never decides the tenant (ADR-163 section 5): the API reads X-Forwarded-Host for
# branding only. Nothing here names a domain: every host comes from variables.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  edge_region  = "us-east-1"
  name         = "abacus-${var.environment}-portal"
  bucket_name  = "abacus-${var.environment}-web-portal"
  account_root = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  web_origin   = "portal-web"
  api_origin   = "api"
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
      values   = [aws_cloudfront_multitenant_distribution.portal.arn]
    }
  }
}

resource "aws_kms_key" "portal" {
  description             = "Encrypts the client portal bundle in ${local.bucket_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "portal" {
  name          = "alias/${local.bucket_name}"
  target_key_id = aws_kms_key.portal.key_id
}

# --- the portal bundle --------------------------------------------------------------------------

# Layout (the deploy path, infra/README.md "Portal edge"): `assets/<hash>.*` (immutable),
# `portal.html` and `runtime-config.json` (no-cache). Nothing from the firm build ever lands here.
resource "aws_s3_bucket" "portal" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_ownership_controls" "portal" {
  bucket = aws_s3_bucket.portal.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "portal" {
  bucket = aws_s3_bucket.portal.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "portal" {
  bucket = aws_s3_bucket.portal.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "portal" {
  bucket = aws_s3_bucket.portal.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.portal.arn
    }
  }
}

# Hashed assets accumulate so a rollback finds the previous bundle's files; replaced entry files
# stay as noncurrent versions for the rollback window.
resource "aws_s3_bucket_lifecycle_configuration" "portal" {
  bucket = aws_s3_bucket.portal.id

  rule {
    id     = "expire-replaced-entries"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.portal]
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "DenyPlainHttp"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.portal.arn, "${aws_s3_bucket.portal.arn}/*"]

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
    resources = ["${aws_s3_bucket.portal.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudfront_multitenant_distribution.portal.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "portal" {
  bucket = aws_s3_bucket.portal.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [aws_s3_bucket_public_access_block.portal]
}

# --- certificate for the default host -----------------------------------------------------------

# Validated by a DNS record in the portal domain's hosted zone (shared account), created by hand
# from `certificate_validation_records`; apply waits here until it validates (infra/README.md).
resource "aws_acm_certificate" "portal" {
  region            = local.edge_region
  domain_name       = "*.${var.portal_base_domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "portal" {
  region          = local.edge_region
  certificate_arn = aws_acm_certificate.portal.arn
}

# --- edge ---------------------------------------------------------------------------------------

resource "aws_cloudfront_function" "entry" {
  name    = "${local.name}-entry"
  runtime = "cloudfront-js-2.0"
  comment = "Portal entry routing, edge-blocked probes, X-Forwarded-Host (Q-01-T56)"
  publish = true
  code    = file("${path.module}/portal-entry.js")
}

resource "aws_cloudfront_origin_access_control" "portal" {
  name                              = local.bucket_name
  description                       = "Client portal bundle"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "api" {
  name = "Managed-AllViewerExceptHostHeader"
}

# Chapter 06 section 1.12 for the portal: HSTS two years with subdomains, nosniff, no referrer,
# no framing, camera for capture (POR-19) and nothing else, and the build's CSP as a header.
resource "aws_cloudfront_response_headers_policy" "portal" {
  name    = "${local.name}-headers"
  comment = "Client portal security headers (Q-01 F4)"

  security_headers_config {
    content_security_policy {
      content_security_policy = var.content_security_policy
      override                = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "no-referrer"
      override        = true
    }

    strict_transport_security {
      access_control_max_age_sec = 63072000
      include_subdomains         = true
      preload                    = false
      override                   = true
    }
  }

  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "camera=(self), microphone=(), geolocation=()"
      override = true
    }
  }
}

resource "aws_cloudfront_multitenant_distribution" "portal" {
  enabled             = true
  comment             = "${local.name}: client portal entry and same-origin /v1"
  http_version        = "http2and3"
  default_root_object = "portal.html"
  web_acl_id          = var.web_acl_arn

  # No per-tenant parameters: every tenant serves the same bundle and API.
  tenant_config {}

  origin {
    id                       = local.web_origin
    domain_name              = aws_s3_bucket.portal.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.portal.id
  }

  origin {
    id          = local.api_origin
    domain_name = var.api_origin_domain_name

    vpc_origin_config {
      vpc_origin_id            = var.api_vpc_origin_id
      origin_read_timeout      = 60
      origin_keepalive_timeout = 60
    }
  }

  # portal.html, runtime-config.json and root files: never cached, so a deploy needs no
  # invalidation.
  default_cache_behavior {
    target_origin_id           = local.web_origin
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.portal.id

    allowed_methods {
      items          = ["GET", "HEAD"]
      cached_methods = ["GET", "HEAD"]
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.entry.arn
    }
  }

  # Content-hashed files: cached for a year.
  cache_behavior {
    path_pattern               = "/assets/*"
    target_origin_id           = local.web_origin
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.portal.id

    allowed_methods {
      items          = ["GET", "HEAD"]
      cached_methods = ["GET", "HEAD"]
    }
  }

  # The API on the same origin (ADR-163 section 4): nothing cached, every viewer header but Host
  # forwarded, Host passed on as X-Forwarded-Host by the function.
  cache_behavior {
    path_pattern               = "/v1/*"
    target_origin_id           = local.api_origin
    viewer_protocol_policy     = "https-only"
    compress                   = false
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.api.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.portal.id

    allowed_methods {
      items          = ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"]
      cached_methods = ["GET", "HEAD"]
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.entry.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.portal.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# Every firm's default host, `<slug>.<portal_base_domain>`, on the distribution's certificate.
resource "aws_cloudfront_distribution_tenant" "default" {
  name            = "${local.name}-default"
  distribution_id = aws_cloudfront_multitenant_distribution.portal.id
  enabled         = true

  domain {
    domain = "*.${var.portal_base_domain}"
  }
}

# The canary custom domain (pen test 1): its own tenant and its own CloudFront-managed
# certificate, served the same portal entry and the same /v1 origin. CloudFront answers the
# certificate's HTTP validation itself, so the domain's CNAME must point at the connection group
# before this is applied (infra/README.md).
resource "aws_cloudfront_distribution_tenant" "canary" {
  count = var.canary_custom_domain == null ? 0 : 1

  name            = "${local.name}-canary"
  distribution_id = aws_cloudfront_multitenant_distribution.portal.id
  enabled         = true

  domain {
    domain = var.canary_custom_domain
  }

  managed_certificate_request {
    primary_domain_name                         = var.canary_custom_domain
    validation_token_host                       = "cloudfront"
    certificate_transparency_logging_preference = "enabled"
  }
}

# --- runtime config and the deploy path ---------------------------------------------------------

# The deploy renders runtime-config.json for portal hosts from this value (platform-ops contract
# section 3.2: `portal_base_domain`, required). Not a secret.
resource "aws_ssm_parameter" "portal_base_domain" {
  name        = "/abacus/${var.environment}/runtime-config/portal_base_domain"
  description = "runtime-config.json portal_base_domain for ${var.environment} (ADR-163)"
  type        = "String"
  value       = var.portal_base_domain
}

# What the deploy role (Q-01-T18) attaches to upload the portal entry: list and put into the
# bundle bucket with its key, and read the runtime-config parameters. No delete: old hashed assets
# stay for rollback. No invalidation: entry files are never cached.
data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "ListPortalBundle"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.portal.arn]
  }

  statement {
    sid       = "PutPortalBundle"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.portal.arn}/assets/*", "${aws_s3_bucket.portal.arn}/portal.html", "${aws_s3_bucket.portal.arn}/runtime-config.json"]
  }

  statement {
    sid       = "EncryptPortalBundle"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [aws_kms_key.portal.arn]
  }

  statement {
    sid     = "ReadRuntimeConfig"
    actions = ["ssm:GetParameter", "ssm:GetParametersByPath"]
    resources = [
      "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter/abacus/${var.environment}/runtime-config",
      "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter/abacus/${var.environment}/runtime-config/*",
    ]
  }
}

resource "aws_iam_policy" "deploy" {
  name        = "${local.name}-deploy"
  description = "Upload the client portal entry (dist/portal) and read its runtime config; attached by the deploy role."
  policy      = data.aws_iam_policy_document.deploy.json
}
