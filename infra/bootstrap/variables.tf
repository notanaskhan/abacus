# Account IDs are never committed (public repository). Supply them in an untracked
# terraform.tfvars; see infra/README.md "Terraform bootstrap (SU-20)".

variable "shared_account_id" {
  description = "12-digit ID of the shared account (state bucket, KMS key, shared OIDC roles)."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.shared_account_id))
    error_message = "shared_account_id must be a 12-digit AWS account ID."
  }
}

variable "staging_account_id" {
  description = "12-digit ID of the staging account, or null until it exists."
  type        = string
  default     = null

  validation {
    condition     = var.staging_account_id == null || can(regex("^[0-9]{12}$", coalesce(var.staging_account_id, "x")))
    error_message = "staging_account_id must be null or a 12-digit AWS account ID."
  }
}

variable "production_account_id" {
  description = "12-digit ID of the production account (also hosts production-dr), or null until it exists."
  type        = string
  default     = null

  validation {
    condition     = var.production_account_id == null || can(regex("^[0-9]{12}$", coalesce(var.production_account_id, "x")))
    error_message = "production_account_id must be null or a 12-digit AWS account ID."
  }
}

variable "staging_profile" {
  description = "AWS SSO profile for the staging account (PlatformAdmin permission set)."
  type        = string
  default     = "staging"
}

variable "production_profile" {
  description = "AWS SSO profile for the production account (time-boxed elevated assignment)."
  type        = string
  default     = "production"
}

variable "github_repo" {
  description = "Repository whose workflows may assume the roles."
  type        = string
  default     = "notanaskhan/abacus"
}

variable "state_bucket_name" {
  description = "Name of the Terraform state bucket. The env backends hard-code the default."
  type        = string
  default     = "abacus-shared-tfstate"
}

variable "region" {
  description = "Primary region (DEC-03, ADR-142)."
  type        = string
  default     = "us-east-2"
}
