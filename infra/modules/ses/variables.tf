variable "environment" {
  description = "Environment name."
  type        = string
}

variable "verified_address" {
  description = "The one address SES (sandbox) sends from and to on staging. Null: no identity."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "Key for the delivery-events queue."
  type        = string
}
