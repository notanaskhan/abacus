# Q-01-T15: the firm edge's WAF (rules 1-7, managed rules in count mode for the first weeks,
# chapter 06 §1.13) with its logs in S3, `authorization` and `cookie` redacted (modules/waf). The
# org's region guard keeps CloudWatch Logs out of us-east-1, so WebACL logs go to an
# `aws-waf-logs-` bucket in us-east-2, written by the log delivery service under its own key.

module "firm_waf_logs" {
  source = "../../modules/waf-logs"
  count  = local.enabled ? 1 : 0

  environment = "staging"
  name        = "firm"
}

module "firm_waf" {
  source = "../../modules/waf"
  count  = local.enabled ? 1 : 0

  name                 = "abacus-staging-firm"
  managed_rules_action = var.firm_managed_rules_action
  enable_logging       = true
  log_destination_arn  = module.firm_waf_logs[0].bucket_arn
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
