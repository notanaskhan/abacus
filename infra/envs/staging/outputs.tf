output "portal_bucket_name" {
  description = "Portal bundle bucket the deploy uploads dist/portal into."
  value       = one(module.portal_edge[*].bucket_name)
}

output "portal_distribution_id" {
  description = "The multi-tenant portal distribution."
  value       = one(module.portal_edge[*].distribution_id)
}

output "portal_certificate_validation_records" {
  description = "Create these in the portal domain's hosted zone (shared account) while the first apply waits."
  value       = one(module.portal_edge[*].certificate_validation_records)
}

output "portal_canary_tenant_id" {
  description = "The canary custom-domain tenant, once portal_canary_custom_domain is set."
  value       = one(module.portal_edge[*].canary_tenant_id)
}

output "portal_deploy_policy_arn" {
  description = "Attach to the staging deploy role (Q-01-T18)."
  value       = one(module.portal_edge[*].deploy_policy_arn)
}

output "portal_runtime_config_parameter" {
  description = "SSM parameter holding portal_base_domain for runtime-config.json."
  value       = one(module.portal_edge[*].runtime_config_parameter)
}

output "exports_bucket_name" {
  description = "The engagement export bucket (ABACUS_EXPORTS_BUCKET)."
  value       = module.exports.bucket_name
}

output "exports_task_environment" {
  description = "Merge into the API and worker task definitions' environment (Q-01-T15)."
  value       = module.exports.task_environment
}
