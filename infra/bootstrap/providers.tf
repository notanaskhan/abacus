locals {
  default_tags = {
    project    = "abacus"
    managed_by = "terraform"
    stack      = "bootstrap"
  }
}

# Credentials come from the shared account's SSO profile (AWS_PROFILE=shared).
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.shared_account_id]

  default_tags {
    tags = local.default_tags
  }
}

# IAM is global, so the region only selects the STS endpoint.
provider "aws" {
  alias               = "staging"
  region              = var.region
  profile             = var.staging_profile
  allowed_account_ids = var.staging_account_id == null ? null : [var.staging_account_id]

  default_tags {
    tags = local.default_tags
  }
}

provider "aws" {
  alias               = "production"
  region              = var.region
  profile             = var.production_profile
  allowed_account_ids = var.production_account_id == null ? null : [var.production_account_id]

  default_tags {
    tags = local.default_tags
  }
}
