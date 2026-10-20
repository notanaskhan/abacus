terraform {
  required_version = "~> 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # State bucket is created by infra/bootstrap. Encryption comes from the bucket's
  # default KMS key, so no encrypt or kms_key_id here (neither needs an account ID).
  backend "s3" {
    bucket       = "abacus-shared-tfstate"
    key          = "envs/shared/terraform.tfstate"
    region       = "us-east-2"
    use_lockfile = true
  }
}
