# The records-destruction role (Q-05-T14; ADR-179 as amended by OQ-1, Q-05-T32; DEC-5823).
# Per-object destruction cannot be a key shred (the ADR-104 envelope keeps each object's wrapped
# key inside the object), so an expired, unheld object version is deleted on the primary evidence
# bucket and its us-west-2 replica, by this role only, and only while a destruction batch runs:
# - assumable only by the worker task role (the batch class runs DestructionExecuteWorkflow),
#   with a `destruction_batch` session tag naming the batch;
# - allowed s3:DeleteObjectVersion (and the reads the re-check needs), never
#   s3:BypassGovernanceRetention, s3:PutObjectLegalHold or any retention or lock change, so S3
#   itself still refuses a version under retention or legal hold (COMPLIANCE mode);
# - any assumption without a batch tag pages on-call (CloudTrail to EventBridge to SNS).

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "AWS"
      identifiers = [var.worker_task_role_arn]
    }

    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/destruction_batch"
      values   = ["?*"]
    }

    condition {
      test     = "ForAllValues:StringEquals"
      variable = "aws:TagKeys"
      values   = ["destruction_batch"]
    }
  }
}

locals {
  buckets = compact([var.evidence_bucket_arn, var.replica_bucket_arn])
  objects = [for b in local.buckets : "${b}/*"]
}

data "aws_iam_policy_document" "destroy" {
  statement {
    sid       = "DeleteExpiredVersions"
    actions   = ["s3:DeleteObjectVersion", "s3:GetObjectVersion", "s3:GetObjectRetention", "s3:GetObjectLegalHold"]
    resources = local.objects

    condition {
      test     = "StringLike"
      variable = "aws:PrincipalTag/destruction_batch"
      values   = ["?*"]
    }
  }

  statement {
    sid       = "ListVersions"
    actions   = ["s3:ListBucketVersions"]
    resources = local.buckets
  }

  statement {
    sid    = "NeverBypassOrChangeLocks"
    effect = "Deny"
    actions = [
      "s3:BypassGovernanceRetention",
      "s3:PutObjectLegalHold",
      "s3:PutObjectRetention",
      "s3:PutBucketObjectLockConfiguration",
      "s3:DeleteBucket",
      "s3:PutBucketPolicy",
      "s3:PutLifecycleConfiguration",
      "s3:GetObject",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "this" {
  name                 = "abacus-${var.environment}-destruction"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
  tags                 = { purpose = "records-destruction", decision = "ADR-179" }
}

resource "aws_iam_role_policy" "destroy" {
  name   = "destroy-expired-versions"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.destroy.json
}

# Any AssumeRole of this role is recorded by CloudTrail; one without the batch tag pages on-call.
resource "aws_cloudwatch_event_rule" "untagged_assume" {
  name        = "abacus-${var.environment}-destruction-untagged-assume"
  description = "The destruction role assumed outside an executing batch (Q-05-T14)"
  event_pattern = jsonencode({
    source      = ["aws.sts"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = ["AssumeRole"]
      requestParameters = {
        roleArn = [aws_iam_role.this.arn]
        tags    = { key = [{ exists = false }] }
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "page" {
  rule = aws_cloudwatch_event_rule.untagged_assume.name
  arn  = var.oncall_topic_arn
}
