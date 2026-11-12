"""T-05-T14 (TASK-7305; SPEC-651 F5; TXP-06 b and d; DEC-4305): E5 part 2, the targeted
waterfall, against T-05-T11's Harborview goldens (written from the screen specs, not this code).

Row acceptance: "Harborview distributes 4,000,000 + 312,000 + 78,000 + 510,000 = 4,900,000, plugs
900,000 and gives the GP 20%." Beginning 704(b) capital per partner is the golden's target less
its plug (100,000 + 2,400,000 + 1,500,000 = 4,000,000, the return of capital)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from abacus.modules.tax.compute.entity.waterfall import (
    Rung,
    WaterfallInvalid,
    WaterfallPartner,
    run_waterfall,
)

GOLDEN: dict[str, Any] = yaml.safe_load(  # Any: the YAML document
    (Path(__file__).parent / "ridgeline_ty2025.yaml").read_text()
)
CASE = GOLDEN["harborview_waterfall"]
KEYS = ("gp", "lp_1", "lp_2")
KINDS = ("gp", "lp", "lp")
RUNGS = (
    Rung(1, "return_of_capital"),
    Rung(2, "preferred_return", {"rate": 8}),
    Rung(3, "catch_up", {"target": 20}),
    Rung(4, "promote", {"gp": 20}),
)


def _partners() -> list[WaterfallPartner]:
    targets = [Decimal(t) for t in CASE["targets"]["parts"]]
    plugs = [Decimal(p) for p in CASE["plugs"]["parts"]]
    return [
        WaterfallPartner(key, kind, target - plug)
        for key, kind, target, plug in zip(KEYS, KINDS, targets, plugs, strict=True)
    ]


def test_harborview_distributes_4_900_000_plugs_900_000_and_gives_the_gp_20_percent() -> None:
    result = run_waterfall(_partners(), RUNGS, Decimal(CASE["plugs"]["expect"]))
    assert [str(r.amount) for r in result.rungs] == CASE["rungs"]["parts"]
    assert str(result.distributable) == CASE["rungs"]["expect"]
    assert [str(result.targets[k]) for k in KEYS] == CASE["targets"]["parts"]
    assert [str(result.plugs[k]) for k in KEYS] == CASE["plugs"]["parts"]
    assert result.rungs[2].shares == {"gp": Decimal(CASE["gp_catch_up"]["gp"])}
    assert result.gp_profit_percent == Decimal(CASE["gp_catch_up"]["expect_percent"])
    assert all(result.checks.values())


def test_the_preview_is_pure_and_the_inputs_hash_follows_the_rungs() -> None:
    first = run_waterfall(_partners(), RUNGS, Decimal(900000))
    again = run_waterfall(_partners(), RUNGS, Decimal(900000))
    edited = run_waterfall(
        _partners(), (*RUNGS[:3], Rung(4, "promote", {"gp": 25})), Decimal(900000)
    )
    assert first.stamp == again.stamp and first.stamp != edited.stamp
    assert edited.plugs["gp"] > first.plugs["gp"] and all(edited.checks.values())


def test_too_little_to_reach_the_promote_stops_at_the_rung_that_runs_out() -> None:
    result = run_waterfall(_partners(), RUNGS, Decimal(200000))  # 4,200,000 distributable
    assert [str(r.amount) for r in result.rungs] == ["4000000", "200000", "0", "0"]
    assert result.plugs["gp"] == 0 and all(result.checks.values())


@pytest.mark.parametrize(
    ("rungs", "code"),
    [
        ((Rung(1, "return_of_capital"),), "undistributed_remainder"),
        (
            (Rung(1, "return_of_capital"), Rung(1, "promote", {"gp": 20})),
            "rung_priorities_must_be_unique",
        ),
        (
            (Rung(1, "return_of_capital"), Rung(2, "catch_up", {"target": 20, "share": 10})),
            "catch_up_share_must_exceed_target",
        ),
        ((Rung(1, "preferred_return", {"rate": 120}),), "rate_out_of_range"),
    ],
)
def test_a_structure_that_cannot_run_is_refused_with_its_code(
    rungs: tuple[Rung, ...], code: str
) -> None:
    with pytest.raises(WaterfallInvalid) as refused:
        run_waterfall(_partners(), rungs, Decimal(900000))
    assert refused.value.code == code
