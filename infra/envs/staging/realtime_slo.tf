# P-10-T51 (DEC-4412): the SSE delivery SLO alarm (SLO-06: outbox commit to client, p95 under 5 s
# over 7 days; a ticket, since the polling fallback covers it) and the database connection
# ceiling the runtime load test holds (under 70% of max_connections). Runbook: RB-28.
#
# The API logs `realtime.delivered` (counts and milliseconds only) on each tail read that hands a
# stream events; `lag_ms` is the oldest event's age on the database clock. The filter turns each
# line into one `SseDeliveryLagMs` sample and the alarm reads its p95.

resource "aws_cloudwatch_log_metric_filter" "sse_delivery_lag" {
  count          = local.enabled ? 1 : 0
  name           = "abacus-staging-sse-delivery-lag"
  log_group_name = module.backend["api"].log_group_name
  pattern        = "{ $.event = \"realtime.delivered\" }"
  metric_transformation {
    name      = "SseDeliveryLagMs"
    namespace = "Abacus/Realtime"
    value     = "$.lag_ms"
    unit      = "Milliseconds"
  }
}

resource "aws_cloudwatch_metric_alarm" "sse_delivery_slo" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-sse-delivery-p95"
  alarm_description   = "SLO-06: SSE delivery p95 over 5 s for 15 minutes; clients fall back to polling. Runbook: docs/runbooks/RB-28-realtime-delivery-degraded.md"
  namespace           = "Abacus/Realtime"
  metric_name         = "SseDeliveryLagMs"
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.sse_delivery_p95_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_cloudwatch_metric_alarm" "db_connections" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-db-connections-70"
  alarm_description   = "Database connections above 70% of max_connections (the runtime load test's ceiling). Runbook: docs/runbooks/RB-28-realtime-delivery-degraded.md"
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = floor(var.db_max_connections * 0.7)
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    DBInstanceIdentifier = "abacus-staging"
  }
  alarm_actions = var.alarm_topic_arns
}
