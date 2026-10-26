# Values come from the untracked terraform.tfvars (terraform.tfvars.example lists them). Nothing
# that identifies an account, a person or a vendor is ever committed: the repository is public.

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
