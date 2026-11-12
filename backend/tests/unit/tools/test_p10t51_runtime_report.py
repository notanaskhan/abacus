"""P-10-T51 (TASK-7428): the runtime load test's verdict from a report and the API's log."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from abacus_tools.loadtest import runtime_report as rr

REPORT = {"groups": [{"name": "stream_first_byte", "p95_ms": 420.0}, {"name": "read_run"}]}


def _lines(lags: list[int]) -> list[str]:
    rows = [json.dumps({"event": "realtime.delivered", "events": 2, "lag_ms": n}) for n in lags]
    return [*rows, "not json", json.dumps({"event": "other", "lag_ms": 99999}), "[]"]


def test_only_delivered_lines_are_samples() -> None:
    assert rr.delivery_lags(_lines([10, 20])) == [10.0, 20.0]


def test_a_run_meeting_every_target() -> None:
    measured = rr.measure(
        REPORT, _lines(list(range(1, 101))), peak_connections=50, max_connections=87
    )
    assert measured.p95_ms == {
        "stream_first_byte": Decimal("420.0"),
        "sse_commit_to_event": Decimal("95.0"),
    }
    assert measured.delivered_reads == 100
    assert rr.verdict(measured) == []
    assert rr.markdown(measured, []).startswith("Met every target.")


def test_each_miss_is_named() -> None:
    measured = rr.measure(
        {"groups": []}, _lines([2500] * 20), peak_connections=70, max_connections=87
    )
    assert rr.verdict(measured) == [
        "stream_first_byte: not measured",
        "sse_commit_to_event: p95 2500.0 ms > 2000 ms",
        "db_connections: peak 70 of 87 >= 70%",
    ]


def test_the_cli_exits_on_the_verdict(tmp_path: Path) -> None:
    report, log = tmp_path / "r.json", tmp_path / "api.log"
    report.write_text(json.dumps(REPORT), encoding="utf-8")
    log.write_text("\n".join(_lines([5, 6, 7])), encoding="utf-8")
    ok = ["--report", str(report), "--api-log", str(log), "--max-connections", "87"]
    assert rr.main([*ok, "--peak-connections", "10"]) == 0
    assert rr.main([*ok, "--peak-connections", "80"]) == 1
    assert rr.main(["--report", str(tmp_path / "missing.json"), "--api-log", str(log),
                    "--peak-connections", "1", "--max-connections", "87"]) == 2  # fmt: skip
