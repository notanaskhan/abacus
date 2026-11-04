# P-11-T22 (DEC-2250): Textract for the OCR port, off until P-11's provider-terms entry is
# approved (`textract_enabled`); the worker runs FakeOcr until then.
module "textract" {
  source = "../../modules/textract"

  enabled                  = var.textract_enabled
  environment              = "staging"
  vpc_id                   = module.network.vpc_id
  subnet_ids               = module.network.app_subnet_ids
  worker_security_group_id = aws_security_group.tasks.id
  worker_role_name         = aws_iam_role.task["worker"].name
  monthly_budget_usd       = var.textract_monthly_budget_usd
  quota_requests           = var.textract_quota_requests
}
