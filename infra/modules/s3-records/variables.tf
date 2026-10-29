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
