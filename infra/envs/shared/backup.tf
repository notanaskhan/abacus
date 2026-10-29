# Q-01-T07 (chapter 06 §6, source code row): a weekly `git bundle` of every branch and tag into
# abacus-shared-backups, kept 12 weeks, written by git-bundle-backup.yml through a role that may
# only put objects under source/ (GitHub OIDC, main only: scheduled runs carry the main ref).
# It protects the code against the loss of the GitHub account.

module "backups" {
  source = "../../modules/s3-private"

  name        = "abacus-shared-backups"
  purpose     = "weekly git bundle of the repository"
  expire_days = 84
}

data "aws_iam_policy_document" "backup_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name                 = "abacus-ci-git-backup"
  description          = "git-bundle-backup.yml: puts the weekly bundle; GitHub OIDC, main only."
  assume_role_policy   = data.aws_iam_policy_document.backup_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "backup" {
  statement {
    sid       = "PutBundle"
    actions   = ["s3:PutObject"]
    resources = ["${module.backups.arn}/source/*"]
  }

  statement {
    sid       = "EncryptBundle"
    actions   = ["kms:GenerateDataKey"]
    resources = [module.backups.key_arn]
  }
}

resource "aws_iam_role_policy" "backup" {
  name   = "put-bundle"
  role   = aws_iam_role.backup.name
  policy = data.aws_iam_policy_document.backup.json
}
