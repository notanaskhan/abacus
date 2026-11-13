"""P-02-T13 (TASK-7723; DEC-4726): the C15 search index's relay lag alarm, read as text (no plan,
no credentials), and the indexer line it counts."""

from __future__ import annotations

from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
SEARCH = (INFRA / "envs" / "staging" / "search.tf").read_text(encoding="utf-8")
VARIABLES = (INFRA / "envs" / "staging" / "variables.tf").read_text(encoding="utf-8")
INDEXER = (
    INFRA.parent / "backend" / "src" / "abacus" / "modules" / "platform" / "search" / "indexer.py"
).read_text(encoding="utf-8")


def _block(name: str) -> str:
    return SEARCH.split(f'"{name}" {{')[1].split("\n}\n")[0]


def test_the_filter_reads_every_backend_services_index_lag_lines() -> None:
    found = _block("search_index_lag")
    assert "for_each       = local.enabled ? local.backend_services : {}" in found
    assert '"{ $.event = \\"search.index_lag\\" }"' in found
    assert 'value     = "$.lag_ms"' in found and '"Milliseconds"' in found
    assert '"search.index_lag"' in INDEXER and "lag_ms=" in INDEXER


def test_the_alarm_is_p95_over_5_seconds_for_15_minutes() -> None:
    alarm = SEARCH.split('resource "aws_cloudwatch_metric_alarm" "search_index_lag" {')[1]
    assert 'extended_statistic  = "p95"' in alarm
    assert "period              = 300" in alarm and "evaluation_periods  = 3" in alarm
    assert "threshold           = var.search_index_lag_p95_ms" in alarm
    assert "default     = 5000" in VARIABLES.split('variable "search_index_lag_p95_ms"')[1]
    assert "RB-31-search-index-drift.md" in alarm
