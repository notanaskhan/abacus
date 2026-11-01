# ac-test-author: ayushkbhatia
"""A-04-T17 (TASK-2905; ADR-078; chapter 10 §10.9.3): the materiality engine's goldens.

Every figure in A-04 §3.3 is asserted with exact Decimal equality against the YAML fixtures here
(transcribed from the plan, never computed): Northwind's three benchmarks and their ranges, the
1.0% and 1.5% options with PM and CT, v2's decided thresholds, v3's final-basis reassessment
(252,900, +700, 0.3%), the prior years and the growth, and Granite Peak's 5% decision. The case
list's SHA-256 is what the CPA review of materiality@1 names
(`docs/quality/golden-reviews/materiality@1.md`).
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml

from abacus.modules.assurance.api import materiality_engine as engine

HERE: Final = Path(__file__).parent
CASES: Final = ("northwind_py2025.yaml", "granite_peak_fy2026.yaml")
REVIEW: Final = HERE.parents[3] / "docs" / "quality" / "golden-reviews" / "materiality@1.md"


def _load(name: str) -> dict[str, Any]:  # Any: YAML
    text = (HERE / name).read_text(encoding="utf-8")
    return cast(dict[str, Any], yaml.safe_load(text))  # Any: YAML


def _policy(p: dict[str, str]) -> engine.Policy:
    return engine.Policy(
        Decimal(p["low"]),
        Decimal(p["high"]),
        Decimal(p["pm_low"]),
        Decimal(p["pm_high"]),
        Decimal(p["ct"]),
        Decimal(p["increment"]),
    )


def case_list_hash() -> str:
    """SHA-256 over the fixtures' bytes in name order: the CPA's review names it."""
    digest = hashlib.sha256()
    for name in sorted(CASES):
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def test_ac3_1_northwind_benchmarks_and_ranges() -> None:
    case = _load("northwind_py2025.yaml")
    for b in case["benchmarks"]:
        row = engine.benchmark(
            engine.BenchmarkInput(
                b["key"],
                b["label"],
                Decimal(b["amount"]),
                Decimal(b["range"][0]),
                Decimal(b["range"][1]),
                "overall" if b["key"] == "net_assets" else "considered_for_specific",
            ),
            rate_pct=Decimal("1.5"),
        )
        assert (row.low, row.high) == (Decimal(b["low"]), Decimal(b["high"])), b["key"]


@pytest.mark.parametrize("name", CASES)
def test_ac3_1_ac3_8_options_with_pm_and_ct_from_the_rounded_overall(name: str) -> None:
    case = _load(name)
    benchmark = case.get("benchmark") or case["benchmarks"][0]
    options = engine.options(
        basis="unadjusted",
        benchmark_key=benchmark["key"],
        benchmark_amount=Decimal(benchmark["amount"]),
        pm_pct=Decimal(case["policy"]["pm_high"]),
        ct_pct=Decimal(case["policy"]["ct"]),
        policy=_policy(case["policy"]),
    )
    computed = {o.key: o.thresholds for o in options if o.thresholds is not None}
    for expected in case["options"]:
        t = computed[expected["key"]]
        assert (t.rate_pct, t.overall, t.pm, t.ct) == (
            Decimal(expected["rate"]),
            Decimal(expected["overall"]),
            Decimal(expected["pm"]),
            Decimal(expected["ct"]),
        ), expected["key"]
    assert [o.key for o in options][-1] == "custom"


@pytest.mark.parametrize("name", CASES)
def test_ac3_4_ac3_8_the_decided_version(name: str) -> None:
    case = _load(name)
    benchmark = case.get("benchmark") or case["benchmarks"][0]
    v2 = case["versions"]["v2"]
    t = engine.thresholds(
        basis="unadjusted",
        benchmark_key=benchmark["key"],
        benchmark_amount=Decimal(benchmark["amount"]),
        rate_pct=Decimal(v2["rate"]),
        pm_pct=Decimal(case["policy"]["pm_high"]),
        ct_pct=Decimal(case["policy"]["ct"]),
        policy=_policy(case["policy"]),
    )
    assert (t.overall, t.pm, t.ct) == (
        Decimal(v2["overall"]),
        Decimal(v2["pm"]),
        Decimal(v2["ct"]),
    )
    assert len(t.stamp.inputs_hash) == 64 and t.stamp.engine_name == "materiality"


def test_ac3_6_the_final_basis_at_the_decided_rate_is_no_change_by_700() -> None:
    case = _load("northwind_py2025.yaml")
    decided = engine.thresholds(
        basis="unadjusted",
        benchmark_key="net_assets",
        benchmark_amount=Decimal(case["benchmarks"][0]["amount"]),
        rate_pct=Decimal("1.5"),
        pm_pct=Decimal("75"),
        ct_pct=Decimal("5"),
        policy=_policy(case["policy"]),
    )
    v3 = case["versions"]["v3_final"]
    found = engine.reassess(decided, final_amount=Decimal(v3["amount"]))
    assert (found.at_rate, found.difference, found.difference_pct) == (
        Decimal(v3["at_rate"]),
        Decimal(v3["difference"]),
        Decimal(v3["difference_pct"]),
    )


def test_ac3_2_prior_years_and_growth_never_move_todays_thresholds() -> None:
    case = _load("northwind_py2025.yaml")
    net = case["benchmarks"][0]
    row = engine.benchmark(
        engine.BenchmarkInput(
            net["key"],
            net["label"],
            Decimal(net["amount"]),
            Decimal("1.0"),
            Decimal("2.0"),
            "overall",
            tuple(
                engine.PriorYear(p["year"], Decimal(p["amount"]), Decimal(p["overall_used"]))
                for p in case["prior_years"]
            ),
        ),
        rate_pct=Decimal("1.5"),
    )
    assert [(p.year, p.at_rate) for p in row.prior_years] == [
        (p["year"], Decimal(p["overall_used"])) for p in case["prior_years"]
    ]
    assert row.growth_pct == Decimal(case["growth_pct"])
    assert (row.low, row.high) == (Decimal(net["low"]), Decimal(net["high"]))


def test_the_cpa_review_names_this_case_list() -> None:
    assert case_list_hash() in REVIEW.read_text(encoding="utf-8")
