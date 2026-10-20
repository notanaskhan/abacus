# One OIDC provider per account (IAM is account-scoped), with per-environment roles.
# Staging and production are skipped until their account IDs are supplied.

module "oidc_shared" {
  source = "../modules/github-oidc"

  github_repo       = var.github_repo
  environments      = ["shared"]
  name_prefix       = local.name_prefix
  state_bucket_arn  = aws_s3_bucket.state.arn
  state_kms_key_arn = aws_kms_key.state.arn
}

module "oidc_staging" {
  source = "../modules/github-oidc"
  count  = var.staging_account_id == null ? 0 : 1

  providers = {
    aws = aws.staging
  }

  github_repo       = var.github_repo
  environments      = ["staging"]
  name_prefix       = local.name_prefix
  state_bucket_arn  = aws_s3_bucket.state.arn
  state_kms_key_arn = aws_kms_key.state.arn
}

module "oidc_production" {
  source = "../modules/github-oidc"
  count  = var.production_account_id == null ? 0 : 1

  providers = {
    aws = aws.production
  }

  github_repo       = var.github_repo
  environments      = ["production", "production-dr"]
  name_prefix       = local.name_prefix
  state_bucket_arn  = aws_s3_bucket.state.arn
  state_kms_key_arn = aws_kms_key.state.arn
}
