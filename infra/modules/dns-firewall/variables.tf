variable "environment" {
  description = "Environment name."
  type        = string
}

variable "vpc_id" {
  description = "The VPC whose resolver the firewall guards."
  type        = string
}

variable "profile" {
  description = "Which allowlist applies: staging or production (main.tf holds both lists)."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.profile)
    error_message = "profile is staging or production."
  }
}

variable "private_zone_names" {
  description = "The VPC's own private zones (Cloud Map namespaces): not egress, so not in the register; each resolves with its subdomains."
  type        = list(string)
  default     = []
}
