# envs/staging

Terraform root for `staging` (staging, us-east-2). State key `envs/staging/terraform.tfstate` in the shared state bucket.

- `portal_edge.tf`: the portal edge (Q-01-T56: `modules/waf` and `modules/cloudfront-portal`). It plans to nothing until `portal_base_domain`, `api_vpc_origin_id` and `api_origin_domain_name` are set in the untracked `terraform.tfvars` (copy `terraform.tfvars.example`). Apply steps: `infra/README.md`, "Portal edge".
- Network, data, compute and the firm edge arrive with Q-01-T14 and T15.
- `exports.tf`: the engagement export bucket (`modules/s3-exports`, DEC-454). Plans on its own; apply steps: `infra/README.md`, "Exports bucket".
