# Q-01-T14: Bedrock through the US Geo inference profiles (ADR-113, ADR-114), for the API and
# worker task roles. Off until Q-02-T44's paid clearance and the provider-terms entry exist
# (`bedrock_enabled`); staging runs the `fake` model route until then.

data "aws_iam_policy_document" "bedrock" {
  statement {
    sid     = "InvokeUsGeo"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse", "bedrock:ConverseStream"]
    resources = [
      "arn:aws:bedrock:us-east-2:${local.account}:inference-profile/us.*",
      "arn:aws:bedrock:us-east-1::foundation-model/*",
      "arn:aws:bedrock:us-east-2::foundation-model/*",
      "arn:aws:bedrock:us-west-2::foundation-model/*",
    ]
  }
}

resource "aws_iam_role_policy" "bedrock" {
  for_each = var.bedrock_enabled ? toset(["api", "worker"]) : toset([])
  name     = "bedrock-us-geo"
  role     = aws_iam_role.task[each.key].name
  policy   = data.aws_iam_policy_document.bedrock.json
}
