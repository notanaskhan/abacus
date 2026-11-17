# A-08-T38 (DEC-5404): the respondent links' alarms. Runbook: RB-91
# (docs/runbooks/RB-91-confirmation-links.md). The API logs `confirm.code_failed` for every wrong or
# refused respondent code and `confirm.expired_view` for every uniform expired view it serves
# (identifiers only: no token, code or address); the workers log `je_scoring.completed` with the
# scoring's milliseconds. Each filter turns a line into one sample.

resource "aws_cloudwatch_log_metric_filter" "confirm_code_failed" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-confirm-code-failed"
  log_group_name = module.backend["api"].log_group_name
  pattern        = "{ $.event = \"confirm.code_failed\" }"
  metric_transformation {
    name      = "ConfirmCodeFailed"
    namespace = "Abacus/Confirmations"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "confirm_code_failed_spike" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-confirm-code-failed-spike"
  alarm_description   = "Respondent code failures above the spike threshold for 10 minutes: guessing or a phishing campaign. Runbook: docs/runbooks/RB-91-confirmation-links.md (RB-91)"
  namespace           = "Abacus/Confirmations"
  metric_name         = "ConfirmCodeFailed"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.confirm_code_failed_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_cloudwatch_log_metric_filter" "confirm_expired_view" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-confirm-expired-view"
  log_group_name = module.backend["api"].log_group_name
  pattern        = "{ $.event = \"confirm.expired_view\" }"
  metric_transformation {
    name      = "ConfirmExpiredView"
    namespace = "Abacus/Confirmations"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "confirm_expired_burst" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-confirm-expired-burst"
  alarm_description   = "A burst of expired-link views (the uniform answer for unknown, expired, revoked and locked tokens): enumeration, or a kill switch left on. Runbook: docs/runbooks/RB-91-confirmation-links.md (RB-91)"
  namespace           = "Abacus/Confirmations"
  metric_name         = "ConfirmExpiredView"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.confirm_expired_burst_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_cloudwatch_log_metric_filter" "je_scoring_duration" {
  for_each       = local.enabled ? { for k, m in module.backend : k => m if startswith(k, "worker") } : {}
  name           = "abacus-staging-je-scoring-duration-${each.key}"
  log_group_name = each.value.log_group_name
  pattern        = "{ $.event = \"je_scoring.completed\" }"
  metric_transformation {
    name      = "JeScoringDurationMs"
    namespace = "Abacus/Fieldwork"
    value     = "$.duration_ms"
    unit      = "Milliseconds"
  }
}

resource "aws_cloudwatch_metric_alarm" "je_scoring_duration" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-je-scoring-p95"
  alarm_description   = "JE scoring p95 above the budget for 15 minutes (a 412,903-line population scores in minutes, not hours). Runbook: docs/runbooks/RB-91-confirmation-links.md (RB-91, JE scoring section)"
  namespace           = "Abacus/Fieldwork"
  metric_name         = "JeScoringDurationMs"
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.je_scoring_p95_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}
