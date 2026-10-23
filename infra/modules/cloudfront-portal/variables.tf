variable "environment" {
  description = "staging or production; names the bucket, key, function, tenants and parameters."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment is staging or production."
  }
}

# ADR-163 section 2: the neutral portal domain is a setting, never a literal in code, and never
# contains the product name in any label.
variable "portal_base_domain" {
  description = "The neutral portal domain; each firm's default host is <slug>.<this>. From the untracked tfvars."
  type        = string

  validation {
    condition     = can(regex("^([a-z0-9]([a-z0-9-]*[a-z0-9])?\\.)+[a-z]{2,}$", var.portal_base_domain))
    error_message = "portal_base_domain is a lower-case DNS name."
  }

  validation {
    condition     = !strcontains(lower(var.portal_base_domain), "accrued")
    error_message = "portal_base_domain must not contain the product name (ADR-163)."
  }
}

variable "canary_custom_domain" {
  description = "One firm custom domain served as its own distribution tenant with a CloudFront-managed certificate (the pen-test canary). Null until its CNAME exists."
  type        = string
  default     = null

  validation {
    condition = var.canary_custom_domain == null ? true : (
      can(regex("^([a-z0-9]([a-z0-9-]*[a-z0-9])?\\.)+[a-z]{2,}$", var.canary_custom_domain))
      && !strcontains(lower(var.canary_custom_domain), "accrued")
      && !endswith(var.canary_custom_domain, ".${var.portal_base_domain}")
    )
    error_message = "canary_custom_domain is a lower-case DNS name outside the neutral portal domain, without the product name."
  }
}

variable "api_vpc_origin_id" {
  description = "CloudFront VPC origin of the internal API load balancer (Q-01-T15)."
  type        = string
}

variable "api_origin_domain_name" {
  description = "DNS name of the internal API load balancer behind that VPC origin (Q-01-T15)."
  type        = string
}

variable "web_acl_arn" {
  description = "WebACL (modules/waf) attached to the distribution and inherited by every tenant."
  type        = string
}

variable "content_security_policy" {
  description = "The portal CSP header; the same directives as the build-time meta in apps/web/vite.config.ts (a test keeps them equal)."
  type        = string
  default     = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"
}

variable "noncurrent_version_days" {
  description = "Days a replaced portal.html or runtime-config.json is kept, so rollback can restore the previous bundle."
  type        = number
  default     = 30
}
