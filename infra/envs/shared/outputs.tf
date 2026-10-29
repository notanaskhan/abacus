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

output "ecr_repository_url" {
  description = "Set vars.ECR_REPOSITORY in GitHub to this (it names the account; never commit it)."
  value       = aws_ecr_repository.backend.repository_url
}

output "build_role_name" {
  description = "Set vars.AWS_BUILD_ROLE to arn:aws:iam::<shared account id>:role/<this>."
  value       = aws_iam_role.build.name
}

output "artifacts_bucket" {
  description = "The release artifacts bucket build.yml and the deploys use."
  value       = aws_s3_bucket.artifacts.id
}
