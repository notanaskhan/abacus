# Portal edge on staging (Q-01-T56; OPS-14 part). Off until the untracked terraform.tfvars names
# the neutral portal domain (F-09-T09) and the API's VPC origin exists (Q-01-T15): with either
# unset, this plans to nothing. Apply is the builder's, by hand (infra/README.md "Portal edge").

locals {
  portal_edge = var.portal_base_domain != null && var.api_vpc_origin_id != null && var.api_origin_domain_name != null
}

module "portal_waf" {
  source = "../../modules/waf"
  count  = local.portal_edge ? 1 : 0

  name                 = "abacus-staging-portal"
  managed_rules_action = var.portal_managed_rules_action
}

module "portal_edge" {
  source = "../../modules/cloudfront-portal"
  count  = local.portal_edge ? 1 : 0

  environment            = "staging"
  portal_base_domain     = var.portal_base_domain
  canary_custom_domain   = var.portal_canary_custom_domain
  api_vpc_origin_id      = var.api_vpc_origin_id
  api_origin_domain_name = var.api_origin_domain_name
  web_acl_arn            = module.portal_waf[0].arn
}
