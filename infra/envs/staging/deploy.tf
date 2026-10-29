# Q-01-T18's deploy role (deploy-staging.yml): GitHub OIDC from the `staging` environment only
# (the environment is limited to main with required reviewers, DEC-360). It registers task
# definitions, rolls the services, runs the migrate task, publishes the SPA and records the
# release; it reads release records and images from the shared account.

data "aws_iam_policy_document" "deploy" {
  statement {
    sid = "Ecs"
    actions = [
      "ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition", "ecs:UpdateService",
      "ecs:DescribeServices", "ecs:RunTask", "ecs:DescribeTasks", "ecs:ListTasks",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "PassTaskRoles"
    actions = ["iam:PassRole"]
    resources = concat(
      [for r in aws_iam_role.task : r.arn],
      [module.cluster.execution_role_arn],
    )
  }

  statement {
    sid       = "Web"
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetObject"]
    resources = [module.web.arn, "${module.web.arn}/*"]
  }

  statement {
    sid       = "WebKey"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [module.kms_platform.key_arn]
  }

  statement {
    sid       = "Invalidate"
    actions   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
    resources = local.enabled ? [module.firm_edge[0].distribution_arn] : ["*"]
  }

  statement {
    sid       = "ReleaseRecordAndLock"
    actions   = ["ssm:GetParameter", "ssm:PutParameter", "ssm:DeleteParameter", "ssm:LabelParameterVersion"]
    resources = ["arn:aws:ssm:${local.region}:${local.account}:parameter/abacus/staging/*"]
  }

  statement {
    sid       = "Alarms"
    actions   = ["cloudwatch:DescribeAlarms"]
    resources = ["*"]
  }

  statement {
    sid       = "SharedArtifacts"
    actions   = ["s3:GetObject", "s3:ListBucket", "s3:PutObject"]
    resources = ["arn:aws:s3:::abacus-shared-artifacts", "arn:aws:s3:::abacus-shared-artifacts/*"]
  }

  dynamic "statement" {
    for_each = var.shared_account_id == null ? [] : [1]
    content {
      sid       = "SharedArtifactsKey"
      actions   = ["kms:Decrypt", "kms:DescribeKey"]
      resources = ["arn:aws:kms:${local.region}:${var.shared_account_id}:key/*"]
    }
  }
}

module "deploy_role" {
  source = "../../modules/deploy-role"
  count  = local.enabled ? 1 : 0

  name               = "abacus-staging-deploy"
  description        = "deploy-staging.yml: roll ECS, run migrate, publish the SPA; GitHub OIDC, environment staging."
  github_repo        = var.github_repo
  github_environment = "staging"
  policy_json        = data.aws_iam_policy_document.deploy.json
}

# Pulling the backend image from the shared ECR needs the shared artifacts key.
data "aws_iam_policy_document" "pull_shared" {
  count = var.shared_account_id == null ? 0 : 1

  statement {
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${local.region}:${var.shared_account_id}:key/*"]
  }
}

resource "aws_iam_role_policy" "pull_shared" {
  count  = var.shared_account_id == null ? 0 : 1
  name   = "pull-shared-image"
  role   = split("/", module.cluster.execution_role_arn)[1]
  policy = data.aws_iam_policy_document.pull_shared[0].json
}
