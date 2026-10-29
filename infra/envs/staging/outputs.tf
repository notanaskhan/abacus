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

output "db_address" {
  description = "RDS hostname (fill-secrets.sh composes the DSNs from it)."
  value       = module.db.address
}

output "firm_host" {
  description = "The firm app's host (CloudFront default domain) until the firm domain exists."
  value       = local.enabled ? module.firm_edge[0].domain_name : null
}

output "github_staging_variables" {
  description = "Values for the staging GitHub environment's variables (names only; compose ARNs outside git)."
  value = local.enabled ? {
    ECS_CLUSTER             = module.cluster.cluster_name
    API_SERVICE             = module.backend["api"].service_name
    WORKER_SERVICES         = join(" ", [for k, m in module.backend : m.service_name if k != "api"])
    MIGRATE_TASK_DEFINITION = module.oneoff["migrate"].family
    OPS_TASK_DEFINITION     = module.oneoff["ops"].family
    TASK_SUBNETS            = join(",", module.network.app_subnet_ids)
    TASK_SECURITY_GROUP     = aws_security_group.tasks.id
    WEB_BUCKET              = module.web.bucket
    FIRM_DISTRIBUTION_ID    = module.firm_edge[0].distribution_id
    SMOKE_BASE_URL          = "https://${module.firm_edge[0].domain_name}"
    DEPLOY_ROLE_NAME        = module.deploy_role[0].role_name
  } : null
}

output "bootstrap_task_definition" {
  description = "Family of the one-off database bootstrap task (Q-01-T20)."
  value       = local.enabled ? module.oneoff["bootstrap"].family : null
}
