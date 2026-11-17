# C-01-T52 (DEC-5415): the hourly QuickBooks ledger sync's alarms. Runbook: RB-92
# (docs/runbooks/RB-92-ledger-sync.md). The background worker logs `ledger_sync.outcome` once per
# entity sync (synced, unchanged, paused, needs_reauth, rate_limited, failed), `ledger_sync.freshness`
# with the minutes since the entity's previous success, and `ledger_sync.meter_budget_exhausted`
# when the firm's monthly Intuit call budget pauses scheduled syncs (codes only, no provider text).

locals {
  ledger_sync_log_group = local.enabled ? (
    var.worker_split ? module.backend["worker-background"].log_group_name : module.backend["worker"].log_group_name
  ) : null
}

resource "aws_cloudwatch_log_metric_filter" "ledger_sync_failed" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-ledger-sync-failed"
  log_group_name = local.ledger_sync_log_group
  pattern        = "{ $.event = \"ledger_sync.outcome\" && $.outcome = \"failed\" }"
  metric_transformation {
    name      = "LedgerSyncFailed"
    namespace = "Abacus/LedgerSync"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "ledger_sync_attempted" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-ledger-sync-attempted"
  log_group_name = local.ledger_sync_log_group
  pattern        = "{ $.event = \"ledger_sync.outcome\" }"
  metric_transformation {
    name      = "LedgerSyncAttempted"
    namespace = "Abacus/LedgerSync"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "ledger_sync_failure_rate" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-ledger-sync-failure-rate"
  alarm_description   = "Ledger sync failures above the rate threshold over an hour (codes in sync_runs). Runbook: docs/runbooks/RB-92-ledger-sync.md (RB-92)"
  evaluation_periods  = 1
  threshold           = var.ledger_sync_failure_rate_pct
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns

  metric_query {
    id          = "rate"
    expression  = "IF(attempted > 0, 100 * failed / attempted, 0)"
    label       = "Failed syncs (%)"
    return_data = true
  }
  metric_query {
    id = "failed"
    metric {
      namespace   = "Abacus/LedgerSync"
      metric_name = "LedgerSyncFailed"
      period      = 3600
      stat        = "Sum"
    }
  }
  metric_query {
    id = "attempted"
    metric {
      namespace   = "Abacus/LedgerSync"
      metric_name = "LedgerSyncAttempted"
      period      = 3600
      stat        = "Sum"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "ledger_sync_freshness" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-ledger-sync-freshness"
  log_group_name = local.ledger_sync_log_group
  pattern        = "{ $.event = \"ledger_sync.freshness\" }"
  metric_transformation {
    name      = "LedgerSyncFreshnessMinutes"
    namespace = "Abacus/LedgerSync"
    value     = "$.minutes"
    unit      = "None"
  }
}

resource "aws_cloudwatch_metric_alarm" "ledger_sync_freshness" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-ledger-sync-freshness"
  alarm_description   = "p95 minutes between an entity's successful syncs above the SLO (60 ± 15) for two hours. Runbook: docs/runbooks/RB-92-ledger-sync.md (RB-92)"
  namespace           = "Abacus/LedgerSync"
  metric_name         = "LedgerSyncFreshnessMinutes"
  extended_statistic  = "p95"
  period              = 3600
  evaluation_periods  = 2
  threshold           = var.ledger_sync_freshness_minutes
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_cloudwatch_log_metric_filter" "ledger_sync_meter_budget" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-ledger-sync-meter-budget"
  log_group_name = local.ledger_sync_log_group
  pattern        = "{ $.event = \"ledger_sync.meter_budget_exhausted\" }"
  metric_transformation {
    name      = "LedgerSyncMeterBudgetExhausted"
    namespace = "Abacus/LedgerSync"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "ledger_sync_meter_budget" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-ledger-sync-meter-budget"
  alarm_description   = "A firm's monthly Intuit call budget paused its scheduled syncs. Runbook: docs/runbooks/RB-92-ledger-sync.md (RB-92)"
  namespace           = "Abacus/LedgerSync"
  metric_name         = "LedgerSyncMeterBudgetExhausted"
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}
