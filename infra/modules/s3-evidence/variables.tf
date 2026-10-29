variable "environment" {
  description = "Environment name."
  type        = string
}

variable "kms_key_arn" {
  description = "Key for SSE-KMS (the platform key)."
  type        = string
}

variable "writer_role_arns" {
  description = "Roles that read and write objects (task roles, the deploy role). Empty until they exist."
  type        = list(string)
  default     = []
}

variable "default_retention_days" {
  description = "GOVERNANCE default retention in days (at least 365)."
  type        = number
  default     = 365

  validation {
    condition     = var.default_retention_days >= 365
    error_message = "Evidence retention is at least 365 days."
  }
}
