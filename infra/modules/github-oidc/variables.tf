variable "github_repo" {
  description = "GitHub repository allowed to assume the roles, as owner/name."
  type        = string
}

variable "environments" {
  description = "Environments whose roles live in this account. Each gets one plan role and one apply role."
  type        = list(string)
}

variable "state_bucket_arn" {
  description = "ARN of the Terraform state bucket (a bucket ARN carries no account ID)."
  type        = string
}

variable "state_kms_key_arn" {
  description = "ARN of the KMS key that encrypts the state bucket."
  type        = string
}

variable "apply_policy_arn" {
  description = "Managed policy attached to the apply roles. Organisation SCPs bound it; narrow it per environment in later tasks."
  type        = string
  default     = "arn:aws:iam::aws:policy/AdministratorAccess"
}

variable "name_prefix" {
  description = "Prefix for role names."
  type        = string
  default     = "abacus-tf"
}
