# P-02-T13 (DEC-4726): the C15 search index's relay lag alarm (P-02 exit: relay lag p95 at or below
# 5 s). The indexer logs `search.index_lag` (object type and milliseconds only, never search text)
# for each document the outbox relay rebuilds; a reindex backfill does not log it. The filter turns
# each line into one `SearchIndexLagMs` sample on whichever backend service ran the relay, and the
# alarm reads its p95. Runbook: RB-82 (index drift and rebuild, P-02-T14; RB-31 was taken).

resource "aws_cloudwatch_log_metric_filter" "search_index_lag" {
  for_each       = local.enabled ? local.backend_services : {}
  name           = "abacus-staging-search-index-lag-${each.key}"
  log_group_name = module.backend[each.key].log_group_name
  pattern        = "{ $.event = \"search.index_lag\" }"
  metric_transformation {
    name      = "SearchIndexLagMs"
    namespace = "Abacus/Search"
    value     = "$.lag_ms"
    unit      = "Milliseconds"
  }
}

resource "aws_cloudwatch_metric_alarm" "search_index_lag" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-search-index-lag-p95"
  alarm_description   = "C15 search index: relay lag p95 over 5 s for 15 minutes; results trail their records. Runbook: docs/runbooks/RB-82-search-index-drift.md"
  namespace           = "Abacus/Search"
  metric_name         = "SearchIndexLagMs"
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.search_index_lag_p95_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}
