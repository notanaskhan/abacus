# Q-01-T07 for F-05 (chapter 04 §9.3): abacus-shared-design-baselines and the CI role that reads
# it through GitHub OIDC on pull requests and main. F-05-T17's visual run renders its baselines on
# the runner from the base commit today (scripts/visual-ci.mjs), so the bucket is where stored
# baselines go once a run needs them (e.g. a base that predates the gallery).

module "design_baselines" {
  source = "../../modules/s3-private"

  name             = "abacus-shared-design-baselines"
  purpose          = "F-05 visual regression baselines"
  reader_role_arns = [aws_iam_role.baselines_ci.arn]
}

data "aws_iam_policy_document" "baselines_trust" {
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
      values   = ["repo:${var.github_repo}:pull_request", "repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "baselines_ci" {
  name                 = "abacus-ci-design-baselines"
  description          = "F-05 CI reads the design baselines; GitHub OIDC, pull requests and main."
  assume_role_policy   = data.aws_iam_policy_document.baselines_trust.json
  max_session_duration = 3600
}
