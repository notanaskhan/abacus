# G-04-T22 (TASK-8759): the staff console's edge on staging. Off until the untracked terraform.tfvars
# names the console host, its issued certificate and at least one allowlisted CIDR: with any unset,
# this plans to nothing. The console build (`vite build --mode console`, dist/console) is served
# from the web bucket with console.html as its entry; staff sign in on the staff issuer (G-04-T14
# rest) with MFA. Apply is the builder's, by hand (infra/README.md "Console edge").

locals {
  console_edge = local.enabled && var.console_host != null && var.console_certificate_arn != null && length(var.console_allow_ipv4_cidrs) > 0
}

module "console_waf" {
  source = "../../modules/waf"
  count  = local.console_edge ? 1 : 0

  name                 = "abacus-staging-console"
  managed_rules_action = var.firm_managed_rules_action
  allow_ipv4_cidrs     = var.console_allow_ipv4_cidrs
  enable_logging       = true
  log_destination_arn  = module.firm_waf_logs[0].bucket_arn
}

module "console_edge" {
  source = "../../modules/cloudfront-firm"
  count  = local.console_edge ? 1 : 0

  environment                = "staging-console"
  web_bucket_regional_domain = module.web.regional_domain_name
  alb_arn                    = aws_lb.api.arn
  alb_dns_name               = aws_lb.api.dns_name
  web_acl_arn                = module.console_waf[0].arn
  firm_host                  = var.console_host
  certificate_arn            = var.console_certificate_arn
  default_root_object        = "console.html"
}
