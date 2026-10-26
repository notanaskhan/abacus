# Engagement export bucket (A-01-T18/T19, DEC-433; DEC-454). Needs nothing else in this root, so it
# plans on its own. The task roles arrive with Q-01-T15: until their names are set in the untracked
# terraform.tfvars the policies exist unattached. Apply is the builder's (infra/README.md
# "Exports bucket").

module "exports" {
  source = "../../modules/s3-exports"

  environment           = "production"
  worker_task_role_name = var.worker_task_role_name
  api_task_role_name    = var.api_task_role_name
}
