variable "environment" {
  description = "Environment name."
  type        = string
}

variable "secret_arns" {
  description = "Secrets the task execution role may read to inject into containers."
  type        = list(string)
}

variable "kms_key_arn" {
  description = "Key the secrets are encrypted with."
  type        = string
}
