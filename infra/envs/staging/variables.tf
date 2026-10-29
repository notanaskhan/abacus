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

variable "worker_task_role_name" {
  description = "Name of the worker ECS task role (Q-01-T15). Null: the exports worker policy is not attached."
  type        = string
  default     = null
}

variable "api_task_role_name" {
  description = "Name of the API ECS task role (Q-01-T15). Null: the exports API policy is not attached."
  type        = string
  default     = null
}

variable "ses_verified_address" {
  description = "The one inbox SES (sandbox) may send to and from on staging (DEC-1003). Null: no email identity."
  type        = string
  default     = null
}

variable "workos_issuer" {
  description = "WorkOS staging environment's token issuer (not a secret)."
  type        = string
  default     = null
}

variable "workos_client_id" {
  description = "WorkOS staging client ID (not a secret)."
  type        = string
  default     = null
}

variable "image_digest" {
  description = "The backend image to run, as <repository url>@sha256:... (from the release record). Null: no services are planned."
  type        = string
  default     = null
}

variable "workos_jwks" {
  description = "WorkOS staging JWKS document (public keys, JSON). Null until WorkOS is set up."
  type        = string
  default     = null
}

variable "shared_account_id" {
  description = "The shared account (release images and records). From the untracked terraform.tfvars."
  type        = string
  default     = null
}

variable "github_repo" {
  description = "Repository whose staging environment may assume the deploy role."
  type        = string
  default     = "notanaskhan/abacus"
}

variable "firm_managed_rules_action" {
  description = "count for the first weeks of the firm WebACL on staging, then block (chapter 06 section 1.13)."
  type        = string
  default     = "count"
}

variable "firm_host" {
  description = "The firm app's host once its domain exists (F-09-T09). Null: CloudFront's default host."
  type        = string
  default     = null
}

variable "firm_certificate_arn" {
  description = "The issued firm certificate (after DNS validation). Null: the default certificate."
  type        = string
  default     = null
}

variable "canary_tenant_id" {
  description = "Tenant id of the synthetic canary firm (Canary & Co, Q-01-T20), for its Terraform-declared key. Null until provisioned."
  type        = string
  default     = null
}

variable "worker_split" {
  description = "Run one worker service per work class (interactive, time_sensitive, background, batch) instead of one for all (minimal sizing, DEC-1003)."
  type        = bool
  default     = false
}
