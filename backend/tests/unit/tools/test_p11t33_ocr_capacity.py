"""P-11-T33 (TASK-6128; DEC-2715): the December x100 OCR load profile and capacity plan.

Row: "December x100 OCR load profile (pages per minute, Textract TPS)"; exit: "OCR meets p95 3
minutes for 20 pages under the December load". The plan is arithmetic over written-down inputs
(RB-68); the scenario is the read side the perf stack plays beside the page drive.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus_tools.loadtest import ocr_capacity as oc
from abacus_tools.loadtest.scenario import profile


def test_ten_firms_at_x100_fit_the_default_quota() -> None:
    result = oc.plan(oc.Inputs(firms=10))
    # 50 pages x 100 = 5,000 a firm a day (exactly the default cap); a fifth in the peak hour:
    # 10,000 pages an hour = 166.67 a minute = 2.78 TPS; FORMS on 30% = 0.84 TPS.
    assert result.pages_per_firm_day == 5000
    assert result.refused_pages_per_firm_day == 0
    assert result.pages_per_minute == Decimal("166.67")
    assert result.detect_tps == Decimal("2.78")
    assert result.analyze_tps == Decimal("0.84")
    assert result.failures == ()


def test_more_firms_than_the_headroom_carries_fail_on_tps() -> None:
    given = oc.Inputs(firms=200)
    assert oc.firms_within_quota(given) == 28  # 8 TPS / (1,000 pages an hour / 3,600)
    failures = oc.plan(given).failures
    assert any("DetectDocumentText" in f for f in failures)


def test_the_cap_refuses_what_x100_reads_past_it() -> None:
    result = oc.plan(oc.Inputs(firms=1, baseline_pages_per_firm_day=80))
    assert (result.pages_per_firm_day, result.capped_pages_per_firm_day) == (8000, 5000)
    assert result.refused_pages_per_firm_day == 3000


def test_twenty_pages_within_three_minutes_at_the_inferred_call_times() -> None:
    result = oc.plan(oc.Inputs(firms=1))
    assert result.twenty_page_seconds == Decimal("74.00")  # (0.5 + 2.0 + 0.3 x 4.0) x 20


def test_slow_calls_fail_the_three_minute_target() -> None:
    slow = oc.Inputs(firms=1, detect_p95_seconds=Decimal("8"))
    assert any("20-page" in f for f in oc.plan(slow).failures)


def test_the_page_cache_lowers_the_drive() -> None:
    cold = oc.plan(oc.Inputs(firms=20))
    warm = oc.plan(oc.Inputs(firms=20, cache_hit_share=Decimal("0.5")))
    assert warm.detect_tps < cold.detect_tps


def test_no_firms_is_refused() -> None:
    with pytest.raises(ValueError, match="firms"):
        oc.plan(oc.Inputs(firms=0))


def test_the_cli_exits_one_on_a_failed_plan(capsys: pytest.CaptureFixture[str]) -> None:
    assert oc.main(["--firms", "10"]) == 0
    assert "PASS" in capsys.readouterr().out
    assert oc.main(["--firms", "500"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_the_december_scenario_loads_read_only_with_ocr_visibility() -> None:
    scenario = profile("ocr_december")
    assert all(s.method == "GET" for g in scenario.groups for s in g.steps)
    assert {g.name for g in scenario.groups} == {"inbox_list", "notices_list", "staff_home"}
    queries = [t.query or "" for t in scenario.temporal]
    assert any("long_ocr" in q for q in queries) and any("ocr_backfill" in q for q in queries)
    assert all(t.kind == "count_workflows" for t in scenario.temporal)
    assert all(g.p95_ms is not None for g in scenario.groups)
