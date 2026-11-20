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

variable "distribution_arn" {
  description = "The firm CloudFront distribution that reads through OAC. Null until it exists."
  type        = string
  default     = null
}

variable "extra_distribution_arns" {
  description = "G-04-T22: other distributions that read the same bucket through OAC (the staff console's). Empty by default."
  type        = list(string)
  default     = []
}
