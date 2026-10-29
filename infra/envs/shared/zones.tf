# Q-01-T07: the public hosted zones for the firm and portal domains (F-09-T09), once they exist.
# Null (today, DEC-1003): no zone; the firm app runs on CloudFront's default host.

resource "aws_route53_zone" "firm" {
  count   = var.firm_domain == null ? 0 : 1
  name    = var.firm_domain
  comment = "Accrued firm app"
}

resource "aws_route53_zone" "portal" {
  count   = var.portal_base_domain == null ? 0 : 1
  name    = var.portal_base_domain
  comment = "Neutral client portal domain (ADR-163)"
}
