"""A-05-T53 (TASK-6110; A-05 F11; AU-C 540): AUD-27's figures are code's.

From A-05 F11, not the code: Granite Peak's inventory reserve $486,000 has components that
foot to TB 1450 (214,000 + 199,000 + 73,000), rolls 412,000 - 398,000 + 472,000, its retrospective
reads 14,000 = 3.4% of 412,000 and 4,500 = 5.4% of 84,000, and the point estimate sits inside the
auditor's range 451,000 to 512,000.
"""

from __future__ import annotations

from decimal import Decimal as D
from uuid import uuid4

import pytest

from abacus.modules.assurance import aud27
from abacus.modules.assurance.compute.ebp import estimates as engine

pytestmark = pytest.mark.asyncio


def _granite_peak() -> tuple[
    engine.Footing | None,
    engine.Rollforward | None,
    tuple[engine.Retrospective, ...],
    engine.RangeCheck | None,
    engine.BiasIndicator,
]:
    return aud27.compute(
        D("486000"),
        [D("214000"), D("199000"), D("73000")],
        {"opening": "412000", "usage": "398000", "additions": "472000"},
        [
            {"label": "FY2024 reserve", "prior_estimate": "412000", "outcome": "398000"},
            {"label": "FY2024 warranty", "prior_estimate": "84000", "outcome": "79500"},
        ],
        D("451000"),
        D("512000"),
    )


def test_f11_components_foot_to_tb_1450() -> None:
    footing = _granite_peak()[0]
    assert footing is not None
    assert footing.components_total == D("486000") and footing.foots


def test_f11_the_rollforward_rolls() -> None:
    rolled = _granite_peak()[1]
    assert rolled is not None
    assert rolled.computed_closing == D("486000") and rolled.rolls


def test_f11_the_retrospective_percentages() -> None:
    first, second = _granite_peak()[2]
    assert (first.difference, first.percent) == (D("14000"), D("3.4"))
    assert (second.difference, second.percent) == (D("4500"), D("5.4"))
    assert first.direction == second.direction == "over"


def test_f11_the_point_estimate_is_inside_the_range_and_bias_is_flagged() -> None:
    checked, indicator = _granite_peak()[3], _granite_peak()[4]
    assert checked is not None and checked.inside
    assert indicator.consistent
    assert indicator.direction == "over" and indicator.count == 2


def test_a_component_that_does_not_foot_shows_its_difference() -> None:
    footing = engine.foot([D("214000"), D("199000")], D("486000"))
    assert footing.difference == D("-73000") and not footing.foots


def test_mixed_directions_are_no_bias_indicator() -> None:
    retros = [
        engine.retrospective("a", D("100"), D("90")),
        engine.retrospective("b", D("100"), D("110")),
    ]
    assert not engine.bias(retros).consistent


def test_a_range_must_run_low_to_high_and_a_zero_estimate_has_no_percentage() -> None:
    with pytest.raises(ValueError):
        engine.range_check(D("512000"), D("451000"), D("486000"))
    with pytest.raises(ValueError):
        engine.percent_of(D("1"), D("0"))


def test_the_card_names_its_estimate_in_the_question_key() -> None:
    estimate = uuid4()
    key = aud27.question_key(estimate)
    assert aud27.estimate_of(key) == estimate
    assert aud27.estimate_of("materiality.overall") is None
    assert len(key) <= 80 and key == key.lower()


async def test_screen_out_needs_a_reason_before_anything_else() -> None:
    with pytest.raises(aud27.ScreenOutReasonRequired):
        await aud27.screen_out(None, uuid4(), uuid4(), "   ")  # type: ignore[arg-type]
