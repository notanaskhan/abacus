# P-11-T29 (DEC-2614): the role `ocr-nightly.yml` assumes to run the OCR suite on real Textract,
# report-only until two passes. GitHub OIDC from the `ocr-nightly` GitHub environment only (the
# deploy-role module's trust); the two synchronous OCR actions in this region, nothing else. A
# GitHub runner is outside the VPC, so unlike the worker's policy there is no endpoint condition;
# the suite sends only its synthetic fixture pages, never client content. Exists only with
# Textract on (`textract_enabled`). The ARN is composed outside git for `vars.OCR_NIGHTLY_ROLE_ARN`.
data "aws_iam_policy_document" "ocr_nightly" {
  statement {
    sid       = "OcrSuiteOnRealTextract"
    actions   = ["textract:DetectDocumentText", "textract:AnalyzeDocument"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [local.region]
    }
  }
  statement {
    sid         = "NothingElse"
    effect      = "Deny"
    not_actions = ["textract:DetectDocumentText", "textract:AnalyzeDocument"]
    resources   = ["*"]
  }
}

module "ocr_nightly_role" {
  source = "../../modules/deploy-role"
  count  = var.textract_enabled ? 1 : 0

  name               = "abacus-staging-ocr-nightly"
  description        = "ocr-nightly.yml: the OCR suite on real Textract (P-11-T29); GitHub OIDC, environment ocr-nightly."
  github_repo        = var.github_repo
  github_environment = "ocr-nightly"
  policy_json        = data.aws_iam_policy_document.ocr_nightly.json
}
