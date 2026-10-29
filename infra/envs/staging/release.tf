# Q-01-T18: what deploy-staging.yml reads besides the release record.
# - The runtime-config inputs (`render_runtime_config` in deploy/scripts/release.sh): the WorkOS
#   authority and client ID, the portal base domain (a reserved `.invalid` host until F-09-T09's
#   domain exists, DEC-1010: the firm app never reads it), and the Sentry DSN once there is one.
# - The API alarms the rolling deploy watches (`API_ALARMS`): either one in alarm rolls the new task
#   set back (ECS deployment alarms). Their runbook is RB-01 (ADR-098).

locals {
  runtime_prefix = "/abacus/staging/runtime-config"
}

resource "aws_ssm_parameter" "runtime_config" {
  for_each = {
    oidc_authority     = coalesce(var.workos_issuer, "https://unset.invalid")
    oidc_client_id     = coalesce(var.workos_client_id, "unset")
    portal_base_domain = coalesce(var.portal_base_domain, "unset.invalid")
  }
  name  = "${local.runtime_prefix}/${each.key}"
  type  = "String"
  value = each.value
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-api-5xx"
  alarm_description   = "API targets answer 5xx. Runbook: docs/runbooks/RB-01-deploy-and-rollback.md"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "api_unhealthy" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "abacus-staging-api-unhealthy"
  alarm_description   = "No healthy API target behind the internal ALB. Runbook: docs/runbooks/RB-01-deploy-and-rollback.md"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HealthyHostCount"
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
}
