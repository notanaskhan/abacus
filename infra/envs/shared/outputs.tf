output "preview_host" {
  description = "Set the repository variable PREVIEW_HOST to this."
  value       = module.previews.host
}

output "preview_ci_role_name" {
  description = "Set the repository variable AWS_PREVIEW_ROLE to arn:aws:iam::<shared account id>:role/<this>."
  value       = module.previews.ci_role_name
}

output "preview_gate_store_name" {
  description = "Put gate-key into this KeyValueStore by hand (infra/README.md)."
  value       = module.previews.gate_store_name
}
