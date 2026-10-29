variable "name" {
  description = "Bucket name (abacus-<env>-<purpose>)."
  type        = string
}

variable "purpose" {
  description = "What the bucket holds, for the key description."
  type        = string
}

variable "reader_role_arns" {
  description = "Roles that may list and read objects."
  type        = list(string)
  default     = []
}

variable "writer_role_arns" {
  description = "Roles that may write objects (and read them)."
  type        = list(string)
  default     = []
}

variable "expire_days" {
  description = "Delete current objects after this many days; null keeps them."
  type        = number
  default     = null
}
