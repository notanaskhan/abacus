"""P-10-T51 (TASK-7422; DEC-4412): the SSE delivery SLO alarm (SLO-06) and the database
connection ceiling, read as text (no plan, no credentials)."""

from __future__ import annotations

from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
SLO = (INFRA / "envs" / "staging" / "realtime_slo.tf").read_text(encoding="utf-8")
VARIABLES = (INFRA / "envs" / "staging" / "variables.tf").read_text(encoding="utf-8")
RUNBOOK = INFRA.parent / "docs" / "runbooks" / "RB-28-realtime-delivery-degraded.md"


def _block(name: str) -> str:
    return SLO.split(f'"{name}" {{')[1].split("\n}\n")[0]


def test_the_filter_reads_the_apis_delivered_lines_as_milliseconds() -> None:
    found = _block("sse_delivery_lag")
    assert 'module.backend["api"].log_group_name' in found
    assert '"{ $.event = \\"realtime.delivered\\" }"' in found
    assert 'value     = "$.lag_ms"' in found and '"Milliseconds"' in found


def test_the_slo_alarm_is_p95_over_5_seconds_for_15_minutes() -> None:
    found = _block("sse_delivery_slo")
    assert 'extended_statistic  = "p95"' in found
    assert "period              = 300" in found and "evaluation_periods  = 3" in found
    assert "threshold           = var.sse_delivery_p95_ms" in found
    assert 'variable "sse_delivery_p95_ms"' in VARIABLES
    assert "default     = 5000" in VARIABLES.split('variable "sse_delivery_p95_ms"')[1]
    assert "RB-28-realtime-delivery-degraded.md" in found


def test_the_connection_alarm_is_70_percent_of_max_connections() -> None:
    found = _block("db_connections")
    assert '"DatabaseConnections"' in found and '"AWS/RDS"' in found
    assert "floor(var.db_max_connections * 0.7)" in found
    assert 'DBInstanceIdentifier = "abacus-staging"' in found


def test_rb28_exists_and_names_both_alarms() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "abacus-staging-sse-delivery-p95" in text
    assert "abacus-staging-db-connections-70" in text
    assert "realtime.sse" in text
