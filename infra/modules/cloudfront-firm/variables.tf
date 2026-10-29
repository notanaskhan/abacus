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
