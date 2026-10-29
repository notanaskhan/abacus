# The firm app's edge (Q-01-T15): one CloudFront distribution on its default *.cloudfront.net
# host until the firm domain exists (DEC-1003). The SPA comes from abacus-<env>-web through origin
# access control; /v1/* goes to the internal ALB through a CloudFront VPC origin (no public
# endpoint). /healthz and /readyz are refused at the edge (the ALB alone probes them). The WAF
# rules and the firm certificate join with the domain.

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "abacus-${var.environment}-web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_vpc_origin" "api" {
  vpc_origin_endpoint_config {
    name                   = "abacus-${var.environment}-api"
    arn                    = var.alb_arn
    http_port              = 80
    https_port             = 443
    origin_protocol_policy = "http-only"

    origin_ssl_protocols {
      items    = ["TLSv1.2"]
      quantity = 1
    }
  }
}

resource "aws_cloudfront_response_headers_policy" "firm" {
  name    = "abacus-${var.environment}-firm-headers"
  comment = "Firm app security headers (Q-01 F4)"

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
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

resource "aws_cloudfront_function" "edge_block" {
  name    = "abacus-${var.environment}-firm-edge-block"
  runtime = "cloudfront-js-2.0"
  comment = "Refuse /healthz and /readyz at the edge"
  publish = true
  code    = <<-JS
    function handler(event) {
      var uri = event.request.uri;
      if (uri === "/healthz" || uri === "/readyz" || uri.indexOf("/healthz/") === 0 || uri.indexOf("/readyz/") === 0) {
        return { statusCode: 404, statusDescription: "Not Found" };
      }
      return event.request;
    }
  JS
}

resource "aws_cloudfront_distribution" "firm" {
  enabled             = true
  comment             = "abacus ${var.environment} firm app"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  http_version        = "http2and3"

  origin {
    origin_id                = "web"
    domain_name              = var.web_bucket_regional_domain
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  origin {
    origin_id   = "api"
    domain_name = var.alb_dns_name

    vpc_origin_config {
      vpc_origin_id = aws_cloudfront_vpc_origin.api.id
    }
  }

  default_cache_behavior {
    target_origin_id           = "web"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.firm.id
    compress                   = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.edge_block.arn
    }
  }

  ordered_cache_behavior {
    path_pattern               = "/v1/*"
    target_origin_id           = "api"
    viewer_protocol_policy     = "https-only"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.firm.id
    compress                   = true
  }

  # The SPA's client routes: a missing object is the app shell.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
  }
}
