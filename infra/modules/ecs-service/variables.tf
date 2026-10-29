variable "environment" {
  description = "Environment name."
  type        = string
}

variable "name" {
  description = "Service name (api, worker, keyops, scanner, temporal) or one-off task name (migrate, bootstrap, ops)."
  type        = string
}

variable "cluster_arn" {
  description = "ECS cluster."
  type        = string
}

variable "execution_role_arn" {
  description = "Task execution role."
  type        = string
}

variable "task_role_arn" {
  description = "Task role (what the process may do in AWS). Null: none."
  type        = string
  default     = null
}

variable "image" {
  description = "Image, always by digest."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "image must be referenced by digest."
  }
}

variable "command" {
  description = "Container command."
  type        = list(string)
  default     = []
}

variable "cpu" {
  description = "Task CPU units."
  type        = number
}

variable "memory" {
  description = "Task memory in MiB."
  type        = number
}

variable "environment_vars" {
  description = "Plain environment variables (nothing secret)."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Environment variable name to Secrets Manager reference (arn or arn:key::)."
  type        = map(string)
  default     = {}
}

variable "port" {
  description = "Container port, or null."
  type        = number
  default     = null
}

variable "read_only_root" {
  description = "Read-only root filesystem with a tmpfs-like scratch volume at /tmp (the backend image)."
  type        = bool
  default     = true
}

variable "user" {
  description = "Container user, or null for the image's own."
  type        = string
  default     = null
}

variable "service" {
  description = "Run as a long-lived service (true) or register the task definition only (one-off tasks)."
  type        = bool
  default     = true
}

variable "subnet_ids" {
  description = "Subnets for the service's tasks."
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "Security groups for the service's tasks."
  type        = list(string)
  default     = []
}

variable "desired_count" {
  description = "Tasks to run."
  type        = number
  default     = 1
}

variable "target_group_arn" {
  description = "ALB target group, or null."
  type        = string
  default     = null
}

variable "discovery_namespace_id" {
  description = "Cloud Map namespace to register the service in, or null."
  type        = string
  default     = null
}

variable "health_check_grace_seconds" {
  description = "Grace before the ALB health check counts."
  type        = number
  default     = 60
}
