output "arn" {
  description = "WebACL ARN, for a distribution's web_acl_id."
  value       = aws_wafv2_web_acl.this.arn
}

output "name" {
  description = "WebACL name (CloudWatch metrics are named after it)."
  value       = aws_wafv2_web_acl.this.name
}
