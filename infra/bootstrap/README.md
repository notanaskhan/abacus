# bootstrap

Applied once, locally, by the builder (never from a session or CI). Creates, in `shared`: the Terraform state bucket (versioned, dedicated KMS key, public access blocked, TLS-only, native S3 locking), and, per account, the GitHub OIDC provider with a read-only plan role (`pull_request` and `main`) and an apply role (`main` only) per environment. Account IDs are variables in an untracked `terraform.tfvars`. Steps: `infra/README.md`, "Terraform bootstrap (SU-20)".
