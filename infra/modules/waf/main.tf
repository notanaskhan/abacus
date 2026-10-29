# WebACL for a CloudFront distribution (chapter 06 section 1.13; Q-01-T15, T56). CloudFront WebACLs
# live in us-east-1, so every resource here sets its region to the edge region rather than taking
# an aliased provider. Rules, in evaluation order:
#   0  auth and code rate: 30 requests per 5 minutes per IP on the auth prefixes; the 31st is
#      blocked with 429 (T56). Always block: it protects sign-in codes from guessing.
#   1  general rate: 2,000 per 5 minutes per IP, block.
#  10  AmazonIpReputationList          } count or block (managed_rules_action): count for two
#  20  CommonRuleSet                   } weeks on a new environment, then block. The body-size
#  21  body size outside upload routes } rule of the common set always counts; rule 21 blocks
#  30  KnownBadInputsRuleSet           } it again everywhere except the upload routes.
#  40  AnonymousIpList: count only (offshore staff and VPN users are legitimate, ADM-03).
# AWS WAF counts rate rules over a sliding window and acts a few seconds after the limit is
# crossed, so a burst can pass slightly more than the limit before the block starts.

locals {
  edge_region = "us-east-1"
  managed     = var.managed_rules_action
  auth_paths  = "^(?:${join("|", var.auth_rate_limit_paths)})"

  managed_groups = [
    { name = "AWSManagedRulesAmazonIpReputationList", priority = 10, count_only = false },
    { name = "AWSManagedRulesKnownBadInputsRuleSet", priority = 30, count_only = false },
    { name = "AWSManagedRulesAnonymousIpList", priority = 40, count_only = true },
  ]
}

resource "aws_wafv2_web_acl" "this" {
  name        = var.name
  description = "Edge rules for ${var.name} (chapter 06 section 1.13)"
  scope       = "CLOUDFRONT"
  region      = local.edge_region

  default_action {
    allow {}
  }

  custom_response_body {
    key          = "rate_limited"
    content_type = "APPLICATION_JSON"
    content      = jsonencode({ detail = "rate_limited" })
  }

  rule {
    name     = "auth-and-code-rate"
    priority = 0

    action {
      block {
        custom_response {
          response_code            = 429
          custom_response_body_key = "rate_limited"
        }
      }
    }

    statement {
      rate_based_statement {
        limit                 = var.auth_rate_limit
        evaluation_window_sec = var.rate_window_seconds
        aggregate_key_type    = "IP"

        scope_down_statement {
          regex_match_statement {
            regex_string = local.auth_paths

            field_to_match {
              uri_path {}
            }

            text_transformation {
              priority = 0
              type     = "URL_DECODE"
            }

            text_transformation {
              priority = 1
              type     = "LOWERCASE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-auth-and-code-rate"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "general-rate"
    priority = 1

    action {
      block {
        custom_response {
          response_code            = 429
          custom_response_body_key = "rate_limited"
        }
      }
    }

    statement {
      rate_based_statement {
        limit                 = var.general_rate_limit
        evaluation_window_sec = var.rate_window_seconds
        aggregate_key_type    = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-general-rate"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 20

    override_action {
      dynamic "none" {
        for_each = local.managed == "block" ? [1] : []
        content {}
      }

      dynamic "count" {
        for_each = local.managed == "count" ? [1] : []
        content {}
      }
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        # Evidence uploads are larger than the rule's 8 KB inspection limit; rule 21 below blocks
        # oversized bodies everywhere else.
        rule_action_override {
          name = "SizeRestrictions_BODY"

          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "body-size-outside-uploads"
    priority = 21

    action {
      dynamic "block" {
        for_each = local.managed == "block" ? [1] : []
        content {}
      }

      dynamic "count" {
        for_each = local.managed == "count" ? [1] : []
        content {}
      }
    }

    statement {
      and_statement {
        statement {
          label_match_statement {
            scope = "LABEL"
            key   = "awswaf:managed:aws:core-rule-set:SizeRestrictions_Body"
          }
        }

        statement {
          not_statement {
            statement {
              regex_match_statement {
                regex_string = var.upload_path_regex

                field_to_match {
                  uri_path {}
                }

                text_transformation {
                  priority = 0
                  type     = "LOWERCASE"
                }
              }
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-body-size"
      sampled_requests_enabled   = true
    }
  }

  dynamic "rule" {
    for_each = local.managed_groups

    content {
      name     = rule.value.name
      priority = rule.value.priority

      override_action {
        dynamic "none" {
          for_each = !rule.value.count_only && local.managed == "block" ? [1] : []
          content {}
        }

        dynamic "count" {
          for_each = rule.value.count_only || local.managed == "count" ? [1] : []
          content {}
        }
      }

      statement {
        managed_rule_group_statement {
          name        = rule.value.name
          vendor_name = "AWS"
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.name}-${rule.value.name}"
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = var.name
    sampled_requests_enabled   = true
  }
}

# Rule 7: logs go to log-archive through Firehose, never with the credentials or session cookies.
resource "aws_wafv2_web_acl_logging_configuration" "this" {
  # A flag, not the ARN: a destination created in the same apply is unknown at plan time.
  count = var.enable_logging ? 1 : 0

  region                  = local.edge_region
  resource_arn            = aws_wafv2_web_acl.this.arn
  log_destination_configs = [var.log_destination_arn]

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }

  redacted_fields {
    single_header {
      name = "cookie"
    }
  }
}
