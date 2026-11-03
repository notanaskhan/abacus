"""A-06-T08 (TASK-3015; A-06 §3 F4; SPEC-642 AC-6; DEC-2064): SUM goldens and properties.

Row acceptance: "backend/tests/golden/sum/ passes with exact Decimal equality, footing and
idempotence properties hold, and the case files record the reviewing CPA." Each case file is
transcribed from the plan; the engine computes; the test compares exactly.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.assurance.compute.sum import Item, Thresholds, evaluate

HERE = Path(__file__).parent
CASES = sorted(HERE.glob("*.yaml"))


def _case(path: Path) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def _items(raw: list[dict[str, object]]) -> list[Item]:
    return [
        Item(
            ref=str(r["ref"]),
            rollover=Decimal(str(r["rollover"])),
            iron_curtain=Decimal(str(r["iron_curtain"])),
            below_ct=bool(r.get("below_ct", False)),
            prior_year=bool(r.get("prior_year", False)),
        )
        for r in raw
    ]


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_ac_each_case_is_exact(path: Path) -> None:
    case = _case(path)
    t = cast(dict[str, str], case["thresholds"])
    result = evaluate(
        _items(cast(list[dict[str, object]], case["items"])),
        Thresholds(Decimal(t["overall"]), Decimal(t["pm"]), Decimal(t["ct"])),
        column_set=cast("str", case["column_set"]),  # pyright: ignore[reportArgumentType] -- the files hold the two sets
    )
    expect = cast(dict[str, object], case["expect"])
    for key in ("rollover", "iron_curtain", "aggregate", "pct_of_pm", "fill_pct_of_overall"):
        assert getattr(result, key) == Decimal(str(expect[key])), (path.stem, key)
    for key in ("ct_tick_pct", "pm_tick_pct"):
        assert getattr(result, key) == Decimal(str(expect[key])), (path.stem, key)
    assert result.approaching_pm is expect["approaching_pm"]
    assert result.above_pm is expect["above_pm"]
    assert list(result.accumulated) == expect["accumulated"]
    assert list(result.below_ct) == expect["below_ct"]


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_ac_each_case_records_its_reviewer(path: Path) -> None:
    assert "CPA" in str(_case(path)["reviewed_by"])


def test_ac_the_memo_names_the_case_list() -> None:
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in CASES)).hexdigest()
    memo = (HERE.parents[3] / "docs" / "quality" / "golden-reviews" / "sum@1.md").read_text(
        encoding="utf-8"
    )
    assert digest in memo, "a case file changed: re-request the CPA review with the new SHA-256"


money = st.decimals(min_value=-1_000_000, max_value=1_000_000, places=2, allow_nan=False)
items = st.lists(st.tuples(money, money, st.booleans()), min_size=0, max_size=12)
T = Thresholds(Decimal("252200"), Decimal("189150"), Decimal("12610"))


def _built(raw: list[tuple[Decimal, Decimal, bool]]) -> list[Item]:
    return [Item(f"M-{n}", r, i, below_ct=b) for n, (r, i, b) in enumerate(raw, start=1)]


@given(items)
def test_property_the_aggregate_foots_to_the_larger_view(
    raw: list[tuple[Decimal, Decimal, bool]],
) -> None:
    result = evaluate(_built(raw), T, column_set="ebp_net_assets")
    counted = [(r, i) for r, i, b in raw if not b]
    assert result.rollover == sum((r for r, _ in counted), Decimal(0))
    assert result.iron_curtain == sum((i for _, i in counted), Decimal(0))
    assert result.aggregate == max(abs(result.rollover), abs(result.iron_curtain))


@given(items)
def test_property_same_inputs_same_hash(raw: list[tuple[Decimal, Decimal, bool]]) -> None:
    a = evaluate(_built(raw), T, column_set="ebp_net_assets")
    b = evaluate(_built(raw), T, column_set="ebp_net_assets")
    assert a == b


@given(items, money)
def test_property_a_below_ct_item_never_moves_the_aggregate(
    raw: list[tuple[Decimal, Decimal, bool]], extra: Decimal
) -> None:
    base = evaluate(_built(raw), T, column_set="ebp_net_assets")
    more = evaluate(
        [*_built(raw), Item("BCT-X", extra, extra, below_ct=True)], T, column_set="ebp_net_assets"
    )
    assert (more.rollover, more.iron_curtain, more.aggregate) == (
        base.rollover,
        base.iron_curtain,
        base.aggregate,
    )
