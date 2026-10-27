variable "environment" {
  description = "The environment the key signs for; it names the alias alias/abacus/<environment>/export-signing."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment is staging or production."
  }
}

variable "worker_task_role_name" {
  description = "Name of the worker ECS task role (Q-01-T15). Null: the policy exists unattached and the key policy grants no signer."
  type        = string
  default     = null
}
