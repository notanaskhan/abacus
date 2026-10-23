output "bucket_name" {
  description = "Portal bundle bucket: the deploy uploads dist/portal here (assets first, then portal.html, then runtime-config.json)."
  value       = aws_s3_bucket.portal.bucket
}

output "distribution_id" {
  description = "The multi-tenant portal distribution."
  value       = aws_cloudfront_multitenant_distribution.portal.id
}

output "distribution_arn" {
  description = "The multi-tenant portal distribution ARN."
  value       = aws_cloudfront_multitenant_distribution.portal.arn
}

output "default_tenant_id" {
  description = "Distribution tenant serving *.<portal_base_domain>."
  value       = aws_cloudfront_distribution_tenant.default.id
}

output "canary_tenant_id" {
  description = "Distribution tenant serving the canary custom domain, or null."
  value       = one(aws_cloudfront_distribution_tenant.canary[*].id)
}

output "certificate_validation_records" {
  description = "DNS records to create in the portal domain's hosted zone (shared account) so the wildcard certificate validates."
  value = [
    for o in aws_acm_certificate.portal.domain_validation_options : {
      name  = o.resource_record_name
      type  = o.resource_record_type
      value = o.resource_record_value
    }
  ]
}

output "deploy_policy_arn" {
  description = "Managed policy the deploy role attaches to upload the portal entry."
  value       = aws_iam_policy.deploy.arn
}

output "runtime_config_parameter" {
  description = "SSM parameter the deploy reads for runtime-config.json portal_base_domain."
  value       = aws_ssm_parameter.portal_base_domain.name
}
