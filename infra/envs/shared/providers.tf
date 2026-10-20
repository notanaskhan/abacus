# Credentials come from the OIDC role of this environment (CI) or an SSO profile.
provider "aws" {
  region = "us-east-2"

  default_tags {
    tags = {
      project     = "abacus"
      managed_by  = "terraform"
      environment = "shared"
    }
  }
}
