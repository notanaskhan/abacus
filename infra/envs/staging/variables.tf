# Values come from the untracked terraform.tfvars (terraform.tfvars.example lists them). None of
# them is a secret, but domains stay out of the repository (ADR-163: a setting, never a literal).

variable "portal_base_domain" {
  description = "The neutral portal domain (F-09-T09). Null: the portal edge is not planned."
  type        = string
  default     = null
}

variable "portal_canary_custom_domain" {
  description = "The canary firm custom domain for pen test 1; null until its CNAME points at the connection group."
  type        = string
  default     = null
}

variable "api_vpc_origin_id" {
  description = "CloudFront VPC origin of the internal API load balancer (Q-01-T15). Null: the portal edge is not planned."
  type        = string
  default     = null
}

variable "api_origin_domain_name" {
  description = "DNS name of the internal API load balancer (Q-01-T15)."
  type        = string
  default     = null
}

variable "portal_managed_rules_action" {
  description = "count for the first two weeks of the portal WebACL on staging, then block (chapter 06 section 1.13)."
  type        = string
  default     = "count"
}

variable "pentest_review_principal_arn" {
  description = "The pen tester's own role ARN for the read-only configuration review (rules of engagement, vault). Null: no review role."
  type        = string
  default     = null
}

variable "pentest_review_external_id" {
  description = "External ID agreed in the rules of engagement (vault)."
  type        = string
  default     = null
  sensitive   = true
}

variable "pentest_review_starts_at" {
  description = "Start of the test window, RFC 3339 UTC."
  type        = string
  default     = null
}

variable "pentest_review_ends_at" {
  description = "End of the test window, RFC 3339 UTC; the role refuses every assume after it."
  type        = string
  default     = null
}
