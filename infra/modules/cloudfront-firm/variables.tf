variable "environment" {
  description = "Environment name."
  type        = string
}

variable "web_bucket_regional_domain" {
  description = "Regional domain of abacus-<env>-web."
  type        = string
}

variable "alb_arn" {
  description = "The internal API load balancer (VPC origin)."
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the internal API load balancer."
  type        = string
}

variable "content_security_policy" {
  description = "The firm app's CSP header (the same directives as the build-time meta in apps/web/vite.config.ts)."
  type        = string
  default     = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"
}

variable "web_acl_arn" {
  description = "WAF WebACL (CLOUDFRONT scope) to attach, or null."
  type        = string
  default     = null
}

variable "firm_host" {
  description = "The firm app's host name once the domain exists, or null (the default CloudFront host)."
  type        = string
  default     = null
}

variable "certificate_arn" {
  description = "ACM certificate (us-east-1) for firm_host, or null."
  type        = string
  default     = null
}

variable "default_root_object" {
  description = "The SPA's entry document: index.html for the firm app, console.html for the staff console (G-04-T22)."
  type        = string
  default     = "index.html"

  validation {
    condition     = contains(["index.html", "console.html"], var.default_root_object)
    error_message = "default_root_object is index.html or console.html."
  }
}
