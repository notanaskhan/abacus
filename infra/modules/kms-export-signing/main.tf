# The environment's export-signing key (G-02-T17, DEC-621; G-02 §4.1, §4.9). An asymmetric KMS key
# (ECC_NIST_P256, SIGN_VERIFY): the worker signs each audit-log export's manifest.json with it
# (kernel/crypto/signing.py: kms:Sign, ECDSA_SHA_256 over the SHA-256 digest), and anyone holding
# the published public key verifies the signature offline:
#   openssl dgst -sha256 -verify export-signing.pem -signature manifest.sig manifest.json
# The private key never leaves KMS. Asymmetric keys cannot rotate automatically: a new key is a new
# alias target, and the old public key stays published for the bundles it signed (7 days).

data "aws_caller_identity" "current" {}

locals {
  alias        = "alias/abacus/${var.environment}/export-signing"
  account      = data.aws_caller_identity.current.account_id
  account_root = "arn:aws:iam::${local.account}:root"
  signer       = var.worker_task_role_name == null ? [] : ["arn:aws:iam::${local.account}:role/${var.worker_task_role_name}"]
}

data "aws_iam_policy_document" "key" {
  # The account administers the key but cannot sign with it: no kms:Sign here, so an IAM policy
  # alone never signs an export (as the exports key, DEC-454).
  statement {
    sid = "KeyAdministration"
    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Get*",
      "kms:Delete*",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
    ]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = [local.account_root]
    }
  }

  # Security review M2: administration (kms:Create*, kms:Put*) could otherwise grant the account a
  # signer. An explicit Deny wins over any grant or later Allow: nobody creates a grant on this key,
  # and nobody but the worker task role signs with it (nobody at all until that role is named).
  statement {
    sid       = "DenyGrants"
    effect    = "Deny"
    actions   = ["kms:CreateGrant"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
  }

  statement {
    sid       = "DenySignExceptWorker"
    effect    = "Deny"
    actions   = ["kms:Sign"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    dynamic "condition" {
      for_each = length(local.signer) > 0 ? [1] : []

      content {
        test     = "StringNotEquals"
        variable = "aws:PrincipalArn"
        values   = local.signer
      }
    }
  }

  # Sign, only by the worker task role, only ECDSA_SHA_256 over a digest.
  dynamic "statement" {
    for_each = length(local.signer) > 0 ? [1] : []

    content {
      sid       = "WorkerSignsDigests"
      actions   = ["kms:Sign"]
      resources = ["*"]

      principals {
        type        = "AWS"
        identifiers = local.signer
      }

      condition {
        test     = "StringEquals"
        variable = "kms:SigningAlgorithm"
        values   = ["ECDSA_SHA_256"]
      }

      condition {
        test     = "StringEquals"
        variable = "kms:MessageType"
        values   = ["DIGEST"]
      }
    }
  }
}

resource "aws_kms_key" "export_signing" {
  description              = "Signs audit-log export manifests (${var.environment})"
  customer_master_key_spec = "ECC_NIST_P256"
  key_usage                = "SIGN_VERIFY"
  deletion_window_in_days  = 30
  policy                   = data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "export_signing" {
  name          = local.alias
  target_key_id = aws_kms_key.export_signing.key_id
}

# The worker's grant on its side: kms:Sign on this key only (the key policy narrows it further).
data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "SignExportManifests"
    actions   = ["kms:Sign"]
    resources = [aws_kms_key.export_signing.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["ECDSA_SHA_256"]
    }
  }

  # The manifest names the key that signs it (its ARN, read before signing; security review).
  # The key policy's administration statement delegates kms:Describe* to IAM.
  statement {
    sid       = "DescribeSigningKey"
    actions   = ["kms:DescribeKey"]
    resources = [aws_kms_key.export_signing.arn]
  }
}

resource "aws_iam_policy" "worker" {
  name        = "abacus-${var.environment}-export-signing-worker"
  description = "Worker task role: sign audit-log export manifests (kms:Sign, ECDSA_SHA_256; kms:DescribeKey)."
  policy      = data.aws_iam_policy_document.worker.json
}

resource "aws_iam_role_policy_attachment" "worker" {
  count = var.worker_task_role_name == null ? 0 : 1

  role       = var.worker_task_role_name
  policy_arn = aws_iam_policy.worker.arn
}
