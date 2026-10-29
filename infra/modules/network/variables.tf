variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
}

variable "cidr" {
  description = "VPC CIDR (chapter 06 section 1.17: staging 10.20.0.0/16)."
  type        = string
}

variable "az_count" {
  description = "Availability zones for the subnets (two: RDS and the ALB need two)."
  type        = number
  default     = 2
}

variable "nat_gateways" {
  description = "NAT gateways (one for staging, one per AZ for production)."
  type        = number
  default     = 1
}

variable "interface_endpoints" {
  description = "AWS services to reach through interface endpoints (e.g. ecr.api, ecr.dkr, logs, secretsmanager, kms, sts, ssm, sqs, email). Empty: through NAT."
  type        = list(string)
  default     = []
}
