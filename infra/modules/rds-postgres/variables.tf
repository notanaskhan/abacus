variable "environment" {
  description = "Environment name."
  type        = string
}

variable "vpc_id" {
  description = "The environment VPC."
  type        = string
}

variable "data_subnet_ids" {
  description = "Data subnets (no route out)."
  type        = list(string)
}

variable "client_security_group_ids" {
  description = "Security groups allowed to connect on 5432 (the ECS tasks)."
  type        = list(string)
  default     = []
}

variable "instance_class" {
  description = "Instance class (staging: the smallest Graviton burstable)."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Initial storage in GiB."
  type        = number
  default     = 20
}

variable "multi_az" {
  description = "Standby in a second zone (production)."
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "Key for storage encryption and the managed master secret."
  type        = string
}

variable "deletion_protection" {
  description = "Refuse deletion (on everywhere but a throwaway drill)."
  type        = bool
  default     = true
}
