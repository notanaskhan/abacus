variable "name" {
  description = "WebACL name, for example abacus-staging-portal."
  type        = string
}

variable "managed_rules_action" {
  description = "count for the first two weeks on a new environment (chapter 06 section 1.13), then block."
  type        = string
  default     = "count"

  validation {
    condition     = contains(["count", "block"], var.managed_rules_action)
    error_message = "managed_rules_action is count or block."
  }
}

variable "general_rate_limit" {
  description = "Requests per IP in the window before the general rate rule blocks (rule 5: 2,000 per 5 minutes)."
  type        = number
  default     = 2000
}

variable "auth_rate_limit" {
  description = "Auth and code requests per IP in the window that are allowed; the next one is blocked (rule 6: 30 per 5 minutes)."
  type        = number
  default     = 30

  validation {
    condition     = var.auth_rate_limit >= 10 && var.auth_rate_limit <= 30
    error_message = "auth_rate_limit is between 10 (the AWS WAF minimum) and 30 (chapter 06 section 1.13)."
  }
}

variable "rate_window_seconds" {
  description = "Evaluation window of both rate rules, in seconds (5 minutes)."
  type        = number
  default     = 300
}

variable "auth_rate_limit_paths" {
  description = "Path prefixes the auth and code rate rule counts: staff sign-in, portal sign-in, code entry and MFA. Lower case; matched after URL decoding."
  type        = list(string)
  default     = ["/v1/auth/", "/v1/portal/auth/"]

  validation {
    condition     = length(var.auth_rate_limit_paths) > 0 && alltrue([for p in var.auth_rate_limit_paths : can(regex("^/[a-z0-9/_-]*$", p))])
    error_message = "Each prefix is a lower-case path starting with /, using letters, digits, /, _ and - only."
  }
}

variable "upload_path_regex" {
  description = "Paths where the common rule set's body-size rule stays count: evidence and portal uploads (rule 2)."
  type        = string
  default     = "^/v1/.*upload"
}

variable "log_destination_arn" {
  description = "Firehose delivery stream (name starting aws-waf-logs-) in log-archive, once it exists (rule 7). Null: no logging configuration yet."
  type        = string
  default     = null
}
