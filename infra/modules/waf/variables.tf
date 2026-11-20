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

variable "webhook_rate_limit" {
  description = "Provider webhook deliveries per IP per window on /v1/webhooks/ (ADR-152, DEC-1281)"
  type        = number
  default     = 300
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

variable "code_path_regex" {
  description = "Public code routes rule 0 (chapter 06 rule 6) also counts, as a lower-cased, URL-decoded path regex: the confirmation respondent's code request and verify (A-08-T38)."
  type        = string
  default     = "^/v1/confirm/[^/]+/code(?:/verify)?$"

  validation {
    condition     = can(regex(var.code_path_regex, "/v1/confirm/abc/code")) && startswith(var.code_path_regex, "^")
    error_message = "code_path_regex is an anchored regex that matches /v1/confirm/<token>/code."
  }
}

variable "stream_path_regex" {
  description = "Server-sent event streams (lower-cased path), not counted by rule 1's general rate (P-10-T15): run, session, badge and invalidation streams (SPEC-647 §3.8)."
  type        = string
  default     = "^/v1/(?:events|me/agent-events|agent-runs/[^/]+/events|workbench/sessions/[^/]+/events)$"
}

variable "upload_path_regex" {
  description = "File routes (lower-cased path): exempt from rule 21's body-size block, rate-limited by rule 3 and capped by rule 22. Evidence and portal uploads, staff-logged intake files, every raw-body import (N-01-T24) and portal drops (R-01-T35)."
  type        = string
  default     = "^/v1/(?:.*upload|.*import|inbox/intake/[^/]+/files$|portal/binders/[^/]+/drops$)"
}

variable "upload_rate_limit" {
  description = "Requests per IP per window on the file routes (rule 3; N-01-T24)"
  type        = number
  default     = 300
}

variable "upload_max_content_length_regex" {
  description = "A Content-Length on a file route this regex matches is refused at the edge with 413 (rule 22): 64,000,000 bytes or more, above the scanner's 60 MiB stream limit and every route's own cap."
  type        = string
  default     = "^(?:[0-9]{9,}|6[4-9][0-9]{6}|[7-9][0-9]{7})$"
}

variable "log_destination_arn" {
  description = "Firehose delivery stream (name starting aws-waf-logs-) in log-archive, once it exists (rule 7). Null: no logging configuration yet."
  type        = string
  default     = null
}

variable "enable_logging" {
  description = "Send WebACL logs to log_destination_arn (rule 7), with authorization and cookie redacted."
  type        = bool
  default     = false
}

variable "allow_ipv4_cidrs" {
  description = "G-04-T22: when non-empty, only these IPv4 CIDRs reach the distribution (the staff console's IP allowlist); every other source is blocked before any other rule. Empty (the default): no allowlist."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.allow_ipv4_cidrs : can(cidrhost(c, 0)) && !strcontains(c, ":")])
    error_message = "Each entry is an IPv4 CIDR, for example 203.0.113.0/24."
  }
}
