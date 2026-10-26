# envs/production

Terraform root for `production` (production, us-east-2). Backend and provider only; resources arrive in later Q-01 tasks (T07 and after). State key `envs/production/terraform.tfstate` in the shared state bucket.
- `exports.tf`: the engagement export bucket (`modules/s3-exports`, DEC-454). Plans on its own; apply steps: `infra/README.md`, "Exports bucket".
