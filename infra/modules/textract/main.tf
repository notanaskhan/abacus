# P-11-T22 (DEC-2250): Amazon Textract inside the AWS boundary for the OCR port (P-11-T23).
# - An interface VPC endpoint in us-east-2 with private DNS: the worker reaches Textract only
#   through it (the role's allow carries aws:SourceVpce; anything else is denied).
# - The background worker's role may call DetectDocumentText and AnalyzeDocument, nothing else in
#   Textract (an explicit deny on every other Textract action, whatever another policy allows).
# - Throttle and error alarms, and a monthly cost budget, to the platform's alarm topic.
# - Quota increase requests for the December x100 load test are explicit inputs (quota codes and
#   values), so a request is reviewed as code, never filed by hand.
# The AWS Organizations AI-services opt-out (infra/landing-zone/ai-services-opt-out.json) is the
# boundary basis: infra/tests/test_textract.py fails if it stops opting every AI service out.

terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

data "aws_region" "current" {}

resource "aws_security_group" "textract" {
  count       = var.enabled ? 1 : 0
  name        = "abacus-${var.environment}-textract-endpoint"
  description = "Textract interface endpoint: HTTPS from the worker tasks only"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "textract_https" {
  count                        = var.enabled ? 1 : 0
  security_group_id            = aws_security_group.textract[0].id
  referenced_security_group_id = var.worker_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "HTTPS from the worker tasks"
}

resource "aws_vpc_endpoint" "textract" {
  count               = var.enabled ? 1 : 0
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.textract"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.textract[0].id]
  tags                = { Name = "abacus-${var.environment}-textract" }
}

data "aws_iam_policy_document" "worker" {
  count = var.enabled ? 1 : 0
  statement {
    sid       = "TextractThroughTheEndpoint"
    actions   = ["textract:DetectDocumentText", "textract:AnalyzeDocument"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceVpce"
      values   = [aws_vpc_endpoint.textract[0].id]
    }
  }
  statement {
    sid         = "NoOtherTextract"
    effect      = "Deny"
    not_actions = ["textract:DetectDocumentText", "textract:AnalyzeDocument"]
    resources   = ["*"]
    condition {
      test     = "StringLike"
      variable = "aws:RequestedService"
      values   = ["textract"]
    }
  }
  statement {
    sid       = "NoTextractOutsideTheEndpoint"
    effect    = "Deny"
    actions   = ["textract:*"]
    resources = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:SourceVpce"
      values   = [aws_vpc_endpoint.textract[0].id]
    }
  }
}

resource "aws_iam_role_policy" "worker" {
  count  = var.enabled ? 1 : 0
  name   = "textract-ocr"
  role   = var.worker_role_name
  policy = data.aws_iam_policy_document.worker[0].json
}

resource "aws_cloudwatch_metric_alarm" "throttled" {
  count               = var.enabled ? 1 : 0
  alarm_name          = "abacus-${var.environment}-textract-throttled"
  alarm_description   = "Textract throttling for the OCR port. Runbook: docs/runbooks/RB-47-ocr-textract.md"
  namespace           = "AWS/Textract"
  metric_name         = "ThrottledCount"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.throttle_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  for_each            = var.enabled ? toset(["UserErrorCount", "ServerErrorCount"]) : toset([])
  alarm_name          = "abacus-${var.environment}-textract-${lower(each.key)}"
  alarm_description   = "Textract ${each.key} for the OCR port. Runbook: docs/runbooks/RB-47-ocr-textract.md"
  namespace           = "AWS/Textract"
  metric_name         = each.key
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.error_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_budgets_budget" "textract" {
  count        = var.enabled ? 1 : 0
  name         = "abacus-${var.environment}-textract"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  cost_filter {
    name   = "Service"
    values = ["Amazon Textract"]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.budget_emails
  }
}

resource "aws_servicequotas_service_quota" "textract" {
  for_each     = var.enabled ? var.quota_requests : {}
  service_code = "textract"
  quota_code   = each.key
  value        = each.value
}
