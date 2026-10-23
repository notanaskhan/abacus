"""The weekly quality report (Q-03-T003): every metric area of chapter 10 §10.14.2 prints, figures
come from the inputs and the repository's tracker files, a missing input reads "no data", and the
report is never written inside the repository."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from abacus_tools.quality import report as rp

WINDOW = rp.Window(date(2027, 1, 11), date(2027, 1, 22))
TRACKER = """# Tracker

| TASK | Zone | Area | Spec | Sprint | Q-03 row | Status | Suite or closing task |
|---|---|---|---|---|---|---|---|
| 075 | red | Boundary | SPEC-036 | S0 | T059 | tranche 0 | x |
| 041 | red | People | SPEC-024 | S6 | T006 | back-filled | x |
| 035 | red | Portal | SPEC-020 | S7 | T014 | scheduled | |
| 028 | amber | Notifications | SPEC-013 | S6 | T065 | superseded | P-01-T14 |
"""
ESCAPED = """# Log

| ID | Found | Sprint | Zone | Path | Introduced by | Found by | Severity \
| Should have been caught by | State | Fix or holding test |
|---|---|---|---|---|---|---|---|---|---|---|
| ED-1 | 2027-01-12 | S6 | red | identity | TASK-041 | Q-03-T006 | SEV4 | integration | fixed | t |
| ED-2 | 2027-01-13 | S6 | red | engagements | TASK-044 | Q-03-T008 | SEV3 | spec | open | t |
| ED-3 | 2026-12-01 | S5 | green | web | TASK-001 | nightly | SEV4 | component | fixed | t |
"""
LEDGER = """# Ledger

| Date | Sprint | Request or move | From → to | te | Why |
|---|---|---|---|---|---|
| 2027-01-14 | S6 | P-07 overrun asked for 1 te | reserve → P-07 | 1 | refused: back-fill not met |
"""


def _repo(tmp_path: Path, *, tracker: bool = True) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "quality").mkdir(parents=True)
    (repo / "docs" / "product").mkdir(parents=True)
    if tracker:
        (repo / "docs" / "quality" / "backfill.md").write_text(TRACKER)
        (repo / "docs" / "quality" / "escaped-defects.md").write_text(ESCAPED)
        (repo / "docs" / "product" / "capacity-ledger.md").write_text(LEDGER)
    tests = repo / "backend" / "tests"
    (tests / "security").mkdir(parents=True)
    (tests / "security" / "test_walls.py").write_text("def test_x(): ...\n")
    (tests / "contracts" / "c16_notifications").mkdir(parents=True)
    (tests / "integration").mkdir()
    (tests / "integration" / "test_backfill.py").write_text(
        "# ac-test-author: ayushkbhatia\nimport pytest\n\n"
        '@pytest.mark.xfail(strict=True, reason="held; recorded (#1)")\ndef test_ac1(): ...\n'
    )
    return repo


def _run(conclusion: str, created: str, updated: str) -> dict[str, str]:
    return {
        "workflowName": "ci",
        "status": "completed",
        "conclusion": conclusion,
        "createdAt": created,
        "updatedAt": updated,
        "event": "push",
    }


def _inputs(tmp_path: Path) -> Path:
    inputs = tmp_path / "inputs"
    (inputs / "evals").mkdir(parents=True)
    runs = [
        _run("success", "2027-01-11T00:00:00Z", "2027-01-11T00:20:00Z"),
        _run("failure", "2027-01-21T00:00:00Z", "2027-01-21T00:30:00Z"),
        _run("cancelled", "2027-01-21T12:00:00Z", "2027-01-21T12:01:00Z"),
        _run("success", "2027-01-22T00:00:00Z", "2027-01-22T00:10:00Z"),
    ]
    (inputs / "runs.json").write_text(json.dumps(runs))
    prs: list[dict[str, object]] = [
        {"number": 1, "additions": 100, "deletions": 50, "createdAt": "2027-01-12T00:00:00Z",
         "mergedAt": "2027-01-12T06:00:00Z", "reviews": []},
        {"number": 2, "additions": 1500, "deletions": 0, "createdAt": "2027-01-13T00:00:00Z",
         "mergedAt": "2027-01-13T02:00:00Z", "reviews": [{"state": "COMMENTED"}]},
        {"number": 3, "additions": 10, "deletions": 0, "createdAt": "2026-12-01T00:00:00Z",
         "mergedAt": "2026-12-01T01:00:00Z", "reviews": []},
    ]  # fmt: skip
    (inputs / "prs.json").write_text(json.dumps(prs))
    coverage = {
        "totals": {"percent_covered": 93.5},
        "files": {
            "src/abacus/modules/identity/service.py": {
                "summary": {"covered_lines": 90, "num_statements": 100}
            },
            "src/abacus/modules/evidence/service.py": {
                "summary": {"covered_lines": 99, "num_statements": 100}
            },
        },
    }
    (inputs / "coverage.json").write_text(json.dumps(coverage))
    parity = {"rows": [
        {"artboard": "SHL-01a", "tier": "A", "diffPercent": 0.0, "status": "passed"},
        {"artboard": "BND-01a", "tier": "B", "diffPercent": 2.0, "status": "failed"},
    ]}  # fmt: skip
    (inputs / "parity.json").write_text(json.dumps(parity))
    (inputs / "journeys.json").write_text(
        json.dumps({"stats": {"expected": 12, "unexpected": 0, "flaky": 1}})
    )
    summary = {"agent": "screener", "status": "passed", "fake": False,
               "total_cost_usd": "3.50", "finished_at": "2027-01-15T03:00:00Z"}  # fmt: skip
    (inputs / "evals" / "screener.json").write_text(json.dumps(summary))
    return inputs


def _row(rows: list[rp.Row], metric_start: str) -> rp.Row:
    return next(r for r in rows if r.metric.startswith(metric_start))


def test_every_metric_area_of_10_14_2_prints_even_with_no_inputs(tmp_path: Path) -> None:
    empty = tmp_path / "none"
    empty.mkdir()
    rows = rp.build(empty, WINDOW, _repo(tmp_path, tracker=False))
    text = rp.render_markdown(rows, WINDOW)
    for area in rp.AREAS:
        assert f"## {area}" in text
        assert any(r.area == area for r in rows), area
    assert len(rp.AREAS) == 12
    assert _row(rows, "Share of time main is green").status == "no data"
    assert _row(rows, "Back-fill burn-down").value == "no data"


def test_main_green_share_is_time_weighted_and_ignores_cancelled_runs(tmp_path: Path) -> None:
    rows = rp.build(_inputs(tmp_path), WINDOW, _repo(tmp_path))
    green = _row(rows, "Share of time main is green")
    # green Jan 11 -> Jan 21 (10 days), red Jan 21 -> Jan 22 (1 day), green Jan 22 -> Jan 23 (1)
    assert green.value.startswith("91.7% over 3 finished runs")
    assert green.status == "breach"


def test_flow_reads_pr_size_escaped_defects_and_refused_reserve(tmp_path: Path) -> None:
    rows = rp.build(_inputs(tmp_path), WINDOW, _repo(tmp_path))
    size = _row(rows, "PR size")
    assert size.value == "825 over 2 merged PRs"
    assert size.status == "breach"
    assert "1 of 2 PRs reviewed" in _row(rows, "Review latency").value
    escaped = _row(rows, "Escaped defects")
    assert escaped.value == "2 (red 2); layers: integration 1, spec 1; 1 open"
    assert escaped.status == "ok"  # the green escape is outside the window
    assert _row(rows, "Reserve requests").value == "1 this window, 1 in all"


def test_tests_area_counts_backfill_coverage_and_held_defects(tmp_path: Path) -> None:
    rows = rp.build(_inputs(tmp_path), WINDOW, _repo(tmp_path))
    burn = _row(rows, "Back-fill burn-down")
    assert burn.value.startswith("1 still owed of 4")
    assert _row(rows, "Coverage, global").status == "breach"
    assert _row(rows, "Coverage, modules below 97%").value == "identity 90.0%"
    assert _row(rows, "Independent AC suites").value == "1"
    assert _row(rows, "Defects held by strict xfail").value == "1"
    assert _row(rows, "Mutation score").status == "no data"


def test_design_journeys_ai_and_cost(tmp_path: Path) -> None:
    rows = rp.build(_inputs(tmp_path), WINDOW, _repo(tmp_path))
    parity = _row(rows, "Parity rows")
    assert parity.value.startswith("2 rows, 1 failed, 0 Tier A/D")
    assert parity.status == "ok"  # a Tier B miss is reported, not blocking
    assert _row(rows, "Journey specs passing").value == "12 passed, 0 failed, 1 flaky"
    assert _row(rows, "Eval suites passing").value == "1 of 1 agents passing"
    assert _row(rows, "Real-model eval spend").value == "$3.50"
    assert _row(rows, "Security test files").value == "1 files"
    assert _row(rows, "Consumer contract suites").value == "1 suites"


def test_the_report_is_never_written_inside_the_repository(tmp_path: Path) -> None:
    inside = rp.REPO / "quality-report.md"
    code = rp.main(["--inputs", str(tmp_path), "--out", str(inside)])
    assert code == 2
    assert not inside.exists()


def test_main_writes_markdown_and_json_outside_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out, rows_json = tmp_path / "report.md", tmp_path / "report.json"
    args = ["--inputs", str(_inputs(tmp_path)), "--since", "2027-01-11", "--until", "2027-01-22"]
    assert rp.main([*args, "--out", str(out), "--json", str(rows_json)]) == 0
    assert out.read_text().startswith("# Quality report, 2027-01-11 to 2027-01-22")
    payload = json.loads(rows_json.read_text())
    assert {row["area"] for row in payload["rows"]} == set(rp.AREAS)
    assert rp.main([*args[:2], "--since", "2027-02-01", "--until", "2027-01-01"]) == 2
    assert "after --until" in capsys.readouterr().err


def test_a_malformed_input_is_an_error_not_a_silent_gap(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "runs.json").write_text("{not json")
    with pytest.raises(rp.ReportError, match=r"runs\.json"):
        rp.build(inputs, WINDOW, _repo(tmp_path))
