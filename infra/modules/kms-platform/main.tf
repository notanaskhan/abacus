# The platform key (Q-01-T14; ADR-104, P-55): a multi-Region symmetric key for platform secrets
# and the export manifests' data keys, aliased alias/abacus/<env>/platform (the app's
# kms_platform_key_alias). Tenant keys are not here: the keyops worker makes them at run time
# (Q-01-T27). The us-west-2 replica is on with `replica` (ADR-142).

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "platform" {
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  dynamic "statement" {
    for_each = length(var.app_role_arns) > 0 ? [1] : []
    content {
      sid       = "AppUse"
      actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
      resources = ["*"]

      principals {
        type        = "AWS"
        identifiers = var.app_role_arns
      }
    }
  }

  # SES publishes delivery events to an encrypted SNS topic, which delivers to an encrypted queue.
  statement {
    sid       = "MessagingServices"
    actions   = ["kms:GenerateDataKey*", "kms:Decrypt"]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com", "sns.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  # RDS encrypts storage and its managed master secret with this key.
  statement {
    sid       = "RdsAndSecrets"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*", "kms:CreateGrant", "kms:DescribeKey", "kms:ReEncrypt*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["rds.${data.aws_region.current.region}.amazonaws.com", "secretsmanager.${data.aws_region.current.region}.amazonaws.com"]
    }
  }
}

data "aws_region" "current" {}

resource "aws_kms_key" "platform" {
  description             = "abacus ${var.environment} platform key"
  multi_region            = true
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.platform.json
}

resource "aws_kms_alias" "platform" {
  name          = "alias/abacus/${var.environment}/platform"
  target_key_id = aws_kms_key.platform.key_id
}

# The us-west-2 replica (ADR-142 DR), on when `replica` is set: same key material, same alias.
resource "aws_kms_replica_key" "platform" {
  count                   = var.replica ? 1 : 0
  region                  = "us-west-2"
  description             = "abacus ${var.environment} platform key (us-west-2 replica)"
  primary_key_arn         = aws_kms_key.platform.arn
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.platform.json
}

resource "aws_kms_alias" "replica" {
  count         = var.replica ? 1 : 0
  region        = "us-west-2"
  name          = "alias/abacus/${var.environment}/platform"
  target_key_id = aws_kms_replica_key.platform[0].key_id
}
