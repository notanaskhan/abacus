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

variable "bedrock_enabled" {
  description = "Let the API and workers call Bedrock through US Geo (after Q-02-T44's clearance)."
  type        = bool
  default     = false
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

variable "third_party_registry" {
  description = "The shared ECR registry host (<account>.dkr.ecr.us-east-2.amazonaws.com) holding the third-party mirrors. Null: Docker Hub."
  type        = string
  default     = null
}

variable "workos_authorize_url" {
  description = "AuthKit authorize endpoint (from the environment's OpenID discovery document). Null: staff sign-in answers 503."
  type        = string
  default     = null
}

variable "workos_token_url" {
  description = "AuthKit token endpoint (from the discovery document)."
  type        = string
  default     = null
}

variable "qbo_enabled" {
  description = "A-02-T33: map the QuickBooks Online sandbox app's secret into the tasks (fill abacus/staging/qbo first)"
  type        = bool
  default     = false
}

variable "docuseal_enabled" {
  description = "TASK-2152: map the DocuSeal key into the ops one-off task (fill abacus/staging/docuseal first)"
  type        = bool
  default     = false
}

variable "docuseal_webhook_enabled" {
  description = "DEC-1281: also map the DocuSeal webhook keys (secret field webhook_keys) into the ops one-off task"
  type        = bool
  default     = false
}
variable "textract_enabled" {
  description = "Create the Textract endpoint and the worker's OCR policy (P-11-T22)."
  type        = bool
  default     = false
}
variable "textract_monthly_budget_usd" {
  description = "The staging Textract cost budget per month."
  type        = string
  default     = "50"
}
variable "textract_quota_requests" {
  description = "Textract quota codes to raise before the December x100 load test (Q-03-T160)."
  type        = map(number)
  default     = {}
}

# P-10-T51 (DEC-4412): the realtime SLO alarms (realtime_slo.tf; RB-28).
variable "sse_delivery_p95_ms" {
  description = "SLO-06: the SSE delivery p95 the alarm allows, in milliseconds."
  type        = number
  default     = 5000
}

variable "search_index_lag_p95_ms" {
  description = "P-02: the C15 search index's relay lag p95 the alarm allows, in milliseconds."
  type        = number
  default     = 5000
}

variable "db_max_connections" {
  description = "The database's max_connections (db.t4g.micro: about 87); the alarm fires above 70% of it."
  type        = number
  default     = 87
}

variable "alarm_topic_arns" {
  description = "SNS topics the realtime alarms notify (none until the paging topic exists)."
  type        = list(string)
  default     = []
}

# A-08-T38 (DEC-5404): the respondent links' and JE scoring's alarm thresholds.
variable "confirm_code_failed_threshold" {
  description = "Respondent code failures per 5 minutes above which RB-91 pages (two periods)."
  type        = number
  default     = 25
}

variable "confirm_expired_burst_threshold" {
  description = "Expired-link views per 5 minutes above which RB-91 pages."
  type        = number
  default     = 100
}

variable "je_scoring_p95_ms" {
  description = "JE scoring p95 in milliseconds above which RB-91's JE section applies."
  type        = number
  default     = 900000
}

# C-01-T52 (RB-92): the ledger sync's alarm thresholds.
variable "ledger_sync_failure_rate_pct" {
  description = "Failed entity syncs as a percent of attempts in an hour above which RB-92 pages."
  type        = number
  default     = 20
}

variable "ledger_sync_freshness_minutes" {
  description = "p95 minutes between an entity's successful syncs above which RB-92 pages (SLO 60 ± 15)."
  type        = number
  default     = 90
}

variable "console_host" {
  description = "G-04-T22: the staff console's host once its domain exists (console.<domain>). Null: no console edge."
  type        = string
  default     = null
}

variable "console_certificate_arn" {
  description = "G-04-T22: the issued us-east-1 certificate for console_host. Null: no console edge."
  type        = string
  default     = null
}

variable "console_allow_ipv4_cidrs" {
  description = "G-04-T22: the only IPv4 CIDRs that reach the console (Accrued staff egress). Empty: no console edge. Set in the untracked terraform.tfvars, never committed."
  type        = list(string)
  default     = []
}

variable "destruction_role_enabled" {
  description = "Q-05-T14: create the records-destruction role (RB-100 proves it on staging first)."
  type        = bool
  default     = false
}

variable "evidence_replica_bucket_arn" {
  description = "Q-05-T14: the us-west-2 replica of the evidence bucket, once it exists."
  type        = string
  default     = null
}

variable "oncall_topic_arn" {
  description = "Q-05-T14: the SNS topic that pages on-call."
  type        = string
  default     = ""
}
