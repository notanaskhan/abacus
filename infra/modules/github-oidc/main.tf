locals {
  oidc_host = "token.actions.githubusercontent.com"

  # pull_request covers PR plans; the main ref covers the nightly drift plan.
  plan_subjects  = ["repo:${var.github_repo}:pull_request", "repo:${var.github_repo}:ref:refs/heads/main"]
  apply_subjects = ["repo:${var.github_repo}:ref:refs/heads/main"]
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = local.plan_subjects
    }
  }
}

data "aws_iam_policy_document" "apply_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = local.apply_subjects
    }
  }
}

# State access: list and read the environment's own prefix; the plan role may only
# write and delete the native lock file (<key>.tflock); the apply role may write state.
data "aws_iam_policy_document" "plan_state" {
  for_each = toset(var.environments)

  statement {
    actions   = ["s3:ListBucket"]
    resources = [var.state_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["envs/${each.key}/*", "envs/${each.key}"]
    }
  }

  statement {
    actions   = ["s3:GetObject"]
    resources = ["${var.state_bucket_arn}/envs/${each.key}/*"]
  }

  statement {
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.state_bucket_arn}/envs/${each.key}/*.tflock"]
  }

  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [var.state_kms_key_arn]
  }
}

data "aws_iam_policy_document" "apply_state" {
  for_each = toset(var.environments)

  statement {
    actions   = ["s3:ListBucket"]
    resources = [var.state_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["envs/${each.key}/*", "envs/${each.key}"]
    }
  }

  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.state_bucket_arn}/envs/${each.key}/*"]
  }

  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [var.state_kms_key_arn]
  }
}

resource "aws_iam_role" "plan" {
  for_each = toset(var.environments)

  name                 = "${var.name_prefix}-plan-${each.key}"
  description          = "Read-only terraform plan for ${each.key}; GitHub OIDC, pull_request and main."
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_read_only" {
  for_each = aws_iam_role.plan

  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "plan_state" {
  for_each = aws_iam_role.plan

  name   = "state-access"
  role   = each.value.name
  policy = data.aws_iam_policy_document.plan_state[each.key].json
}

resource "aws_iam_role" "apply" {
  for_each = toset(var.environments)

  name                 = "${var.name_prefix}-apply-${each.key}"
  description          = "Terraform apply for ${each.key}; GitHub OIDC, main branch only."
  assume_role_policy   = data.aws_iam_policy_document.apply_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "apply_managed" {
  for_each = aws_iam_role.apply

  role       = each.value.name
  policy_arn = var.apply_policy_arn
}

resource "aws_iam_role_policy" "apply_state" {
  for_each = aws_iam_role.apply

  name   = "state-access"
  role   = each.value.name
  policy = data.aws_iam_policy_document.apply_state[each.key].json
}
