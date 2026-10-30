# The DNS Firewall allowlist (Q-01-T14; SPEC-050 AC-22; chapter 06 §1.17): the VPC resolver answers
# only for the allowed domains and the VPC's own private names; every other lookup gets NXDOMAIN, so
# a task cannot reach a host nobody registered. Fails open only if the firewall itself is down
# (`firewall_fail_open` off: closed).

# The registered egress hosts per environment. Every entry has a row in
# docs/operations/sub-processors.yaml (make check-generated). Without interface endpoints
# (DEC-1003) the AWS APIs resolve through *.amazonaws.com. The pinned ClamAV and Temporal images come
# from the shared ECR mirrors, not Docker Hub (DEC-1008). Production adds Temporal Cloud.
locals {
  staging_domains = [
    "*.amazonaws.com",
    "api.docuseal.com",
    "api.workos.com",
    "database.clamav.net",
    "docuseal.com",
  ]
  production_domains = [
    "*.amazonaws.com",
    "api.workos.com",
    "database.clamav.net",
    "*.tmprl.cloud",
  ]
  allowed = var.profile == "production" ? local.production_domains : local.staging_domains
}

resource "aws_route53_resolver_firewall_domain_list" "allowed" {
  name    = "abacus-${var.environment}-allowed"
  domains = concat(local.allowed, flatten([for z in var.private_zone_names : [z, "*.${z}"]]))
}

# Every name (the block rule's list). Not an egress host: a local, so the register scan skips it.
locals {
  every_name = ["*"]
}

resource "aws_route53_resolver_firewall_domain_list" "everything" {
  name    = "abacus-${var.environment}-everything"
  domains = local.every_name
}

resource "aws_route53_resolver_firewall_rule_group" "this" {
  name = "abacus-${var.environment}-egress"
}

resource "aws_route53_resolver_firewall_rule" "allow" {
  name                    = "allow-registered"
  action                  = "ALLOW"
  firewall_domain_list_id = aws_route53_resolver_firewall_domain_list.allowed.id
  firewall_rule_group_id  = aws_route53_resolver_firewall_rule_group.this.id
  priority                = 100
}

resource "aws_route53_resolver_firewall_rule" "block" {
  name                    = "block-everything-else"
  action                  = "BLOCK"
  block_response          = "NXDOMAIN"
  firewall_domain_list_id = aws_route53_resolver_firewall_domain_list.everything.id
  firewall_rule_group_id  = aws_route53_resolver_firewall_rule_group.this.id
  priority                = 200
}

resource "aws_route53_resolver_firewall_rule_group_association" "this" {
  name                   = "abacus-${var.environment}"
  firewall_rule_group_id = aws_route53_resolver_firewall_rule_group.this.id
  vpc_id                 = var.vpc_id
  priority               = 101
}

resource "aws_route53_resolver_firewall_config" "this" {
  resource_id        = var.vpc_id
  firewall_fail_open = "DISABLED"
}
