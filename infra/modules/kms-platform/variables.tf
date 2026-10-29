variable "environment" {
  description = "Environment name."
  type        = string
}

variable "app_role_arns" {
  description = "Task roles that use the platform key (encrypt, decrypt, data keys). Empty until the compute roles exist."
  type        = list(string)
  default     = []
}

variable "replica" {
  description = "Replicate the platform key to us-west-2 (DR)."
  type        = bool
  default     = true
}
