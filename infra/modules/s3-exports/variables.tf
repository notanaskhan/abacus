variable "environment" {
  description = "The environment the bucket serves; it names the bucket abacus-<environment>-exports."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment is staging or production."
  }
}

variable "expiry_days" {
  description = "Days after which an export segment expires (A-01 section 4.1, P-14: a transient copy kept 7 days)."
  type        = number
  default     = 7

  validation {
    condition     = var.expiry_days >= 1 && var.expiry_days <= 7
    error_message = "expiry_days is between 1 and 7: an export is a transient copy, never a record."
  }
}

variable "worker_task_role_name" {
  description = "Name of the worker ECS task role (Q-01-T15). Null: the worker policy is created but not attached."
  type        = string
  default     = null
}

variable "api_task_role_name" {
  description = "Name of the API ECS task role (Q-01-T15). Null: the API policy is created but not attached."
  type        = string
  default     = null
}
