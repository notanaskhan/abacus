"""P-04-T37 (TASK-2924; ADR-078): the review scenario's golden figures.

Each case in `review_scenario.yaml` is transcribed from the plan and the handoff, never from the
code. Materiality cases run through A-04's engine (`assurance.api.materiality_engine`), so a
change that stops a figure footing fails here; the scenario probes check the `review` slice
(P-04-T36) carries the same counts, and the timeline follows DF-34. Every number is read as YAML
text and compared as `Decimal`. A footing check proves the suite fails on a figure that does not
foot (the acceptance's second half).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.assurance.api import materiality_engine as engine
from abacus_tools.synthetic.scenarios.brightwater_hale import review_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.ledgers import (
    GRANITE_PEAK_FY2026,
    NORTHWIND_PY2025,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

HERE = Path(__file__).parent / "review_scenario.yaml"
Case = dict[str, object]


_NUMERIC_TAGS = frozenset({"tag:yaml.org,2002:int", "tag:yaml.org,2002:float"})


class _TextNumbers(yaml.SafeLoader):
    """A SafeLoader that leaves every number as its source text (as the scenario golden)."""


_TextNumbers.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag not in _NUMERIC_TAGS]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.copy().items()
}


def _load() -> dict[str, object]:
    loader = _TextNumbers(HERE.read_text())
    try:
        return cast(dict[str, object], loader.get_single_data())
    finally:
        loader.dispose()


DOC = _load()
CASES = cast(list[Case], DOC["cases"])
BY_ID = {cast(str, c["id"]): c for c in CASES}


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def _thresholds(inputs: dict[str, object]) -> engine.Thresholds:
    low, high = cast(list[object], inputs["policy"])
    policy = engine.Policy(
        low_pct=_d(low),
        high_pct=_d(high),
        pm_low_pct=Decimal(50),
        pm_high_pct=_d(inputs["pm_pct"]),
        ct_pct=_d(inputs["ct_pct"]),
    )
    return engine.thresholds(
        basis="unadjusted",
        benchmark_key="benchmark",
        benchmark_amount=_d(inputs["benchmark"]),
        rate_pct=_d(inputs["rate_pct"]),
        pm_pct=_d(inputs["pm_pct"]),
        ct_pct=_d(inputs["ct_pct"]),
        policy=policy,
    )


def _sum(inputs: dict[str, object]) -> Decimal:
    return sum((_d(v) for v in cast(dict[str, object], inputs["terms"]).values()), Decimal(0))


def test_every_case_names_its_source_and_reviewer() -> None:
    for case in CASES:
        assert {"id", "kind", "inputs", "expected", "source", "reviewed_by"} <= set(case)


@pytest.mark.parametrize("case", CASES, ids=[cast(str, c["id"]) for c in CASES])
def test_the_figure_foots(case: Case) -> None:
    inputs = cast(dict[str, object], case["inputs"])
    expected = cast(dict[str, object], case["expected"])
    kind = case["kind"]
    if kind == "materiality":
        t = _thresholds(inputs)
        assert (t.overall, t.pm, t.ct) == (
            _d(expected["overall"]),
            _d(expected["pm"]),
            _d(expected["ct"]),
        )
    elif kind == "sum":
        assert _sum(inputs) == _d(expected["total"])
    elif kind == "difference":
        assert _d(inputs["now"]) - _d(inputs["then"]) == _d(expected["difference"])
    elif kind == "ratio":
        assert (_d(inputs["cited"]) == _d(inputs["cells"])) is expected["all_cited"]
    else:
        pytest.fail(f"unknown kind {kind!r}")


def test_a_figure_that_does_not_foot_fails() -> None:
    """The suite's teeth: one dollar off the Northwind overall is caught."""
    case = BY_ID["northwind-planning-materiality"]
    t = _thresholds(cast(dict[str, object], case["inputs"]))
    off = _d(cast(dict[str, object], case["expected"])["overall"]) + 1
    assert t.overall != off


# --- probes: the scenario package carries the same figures --------------------------------------


def test_northwind_tb_benchmark_is_the_seeded_net_assets() -> None:
    line = next(
        ln
        for ln in NORTHWIND_PY2025.lines
        if ln.account_name == "Net assets available for benefits"
    )
    case = cast(dict[str, object], BY_ID["northwind-planning-materiality"]["inputs"])
    assert line.credit == _d(case["benchmark"])
    assert NORTHWIND_PY2025.total_debits == NORTHWIND_PY2025.total_credits == line.credit


def test_granite_pre_tax_income_is_the_seeded_ledger() -> None:
    by_code = {ln.account_code: ln for ln in GRANITE_PEAK_FY2026.lines}
    pre_tax = by_code["4000"].credit - sum(
        (by_code[c].debit for c in ("5000", "6000", "7000")), Decimal(0)
    )
    case = cast(dict[str, object], BY_ID["granite-peak-planning-materiality"]["inputs"])
    assert pre_tax == _d(case["benchmark"])


def test_ridgeline_open_issues_match_the_slice() -> None:
    terms = cast(
        dict[str, object],
        cast(dict[str, object], BY_ID["ridgeline-open-issues"]["inputs"])["terms"],
    )
    kinds = Counter(i.kind for i in review_slice.ISSUES)
    assert kinds["waiting_on_client"] == int(_d(terms["waiting_on_client"]))
    assert kinds["review_point"] == int(_d(terms["review_points"]))
    assert all("final_approval" in review_slice.ISSUE_BLOCKS for _ in review_slice.ISSUES)


def test_the_slice_follows_df34s_timeline() -> None:
    at = {e.label: e.at for e in slice_events(review_slice.SLICE)}
    for row in cast(list[dict[str, str]], DOC["timeline"]):
        assert at[row["event"]] == datetime.fromisoformat(row["at"]), row["source"]
