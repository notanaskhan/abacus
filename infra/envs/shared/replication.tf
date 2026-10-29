# Q-01-T07: every pushed image is replicated to us-west-2 (DR, ADR-142) in this account, and to the
# production account once its ID is in terraform.tfvars (its registry policy, Q-01-T28, must allow
# the shared account to replicate).

resource "aws_ecr_replication_configuration" "this" {
  replication_configuration {
    rule {
      destination {
        region      = "us-west-2"
        registry_id = data.aws_caller_identity.current.account_id
      }

      dynamic "destination" {
        for_each = var.production_account_id == null ? [] : [var.production_account_id]
        content {
          region      = "us-east-2"
          registry_id = destination.value
        }
      }

      repository_filter {
        filter      = "abacus-backend"
        filter_type = "PREFIX_MATCH"
      }
    }
  }
}
