# Names only. The ARN is arn:aws:iam::<account id>:role/<name>; compose it outside git.

output "state_bucket_name" {
  description = "Name of the Terraform state bucket (hard-coded in the env backends)."
  value       = aws_s3_bucket.state.id
}

output "state_kms_alias" {
  description = "Alias of the state encryption key."
  value       = aws_kms_alias.state.name
}

output "plan_role_names" {
  description = "Read-only plan role name by environment. Set vars.AWS_PLAN_ROLE_<ENV> to the full ARN."
  value = merge(concat(
    [module.oidc_shared.plan_role_names],
    module.oidc_staging[*].plan_role_names,
    module.oidc_production[*].plan_role_names,
  )...)
}

output "apply_role_names" {
  description = "Main-only apply role name by environment."
  value = merge(concat(
    [module.oidc_shared.apply_role_names],
    module.oidc_staging[*].apply_role_names,
    module.oidc_production[*].apply_role_names,
  )...)
}
