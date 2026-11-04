"""A-04-T31 (TASK-3256; SPEC-620 AC7.1, AC7.2; DEC-2236): SOC 1 evaluation.

Row acceptance: "Keystone shows a 92-day gap, raising the reliance card returns 409 gap_open
until the Sep 22 bridge letter is received, and the Sep 29 reliance decision is Margaret's."
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from abacus.modules.assurance import soc_reports as sr
from abacus.modules.assurance.compute import soc_gap

PLAN_YEAR = {"plan_year_start": date(2025, 1, 1), "plan_year_end": date(2025, 12, 31)}
KEYSTONE = {"period_start": date(2024, 10, 1), "period_end": date(2025, 9, 30)}


def test_ac7_1_keystone_shows_a_92_day_gap_oct_1_to_dec_31() -> None:
    g = soc_gap.gap(**PLAN_YEAR, **KEYSTONE, bridge_received=False)
    assert (g.start, g.end, g.days, g.bridged) == (
        date(2025, 10, 1),
        date(2025, 12, 31),
        92,
        False,
    )
    assert g.stamp.engine_name == "soc_gap" and len(g.stamp.inputs_hash) == 64


def test_a_bridge_letter_bridges_the_gap_without_shrinking_it() -> None:
    g = soc_gap.gap(**PLAN_YEAR, **KEYSTONE, bridge_received=True)
    assert (g.days, g.bridged) == (92, True)


@pytest.mark.parametrize(
    ("start", "end", "days"),
    [
        (date(2025, 1, 1), date(2025, 12, 31), 0),
        (date(2025, 4, 1), date(2026, 3, 31), 90),
        (date(2025, 2, 1), date(2025, 11, 30), 31 + 31),
        (date(2023, 1, 1), date(2023, 12, 31), 365),
    ],
)
def test_the_gap_counts_every_uncovered_plan_year_day(start: date, end: date, days: int) -> None:
    g = soc_gap.gap(**PLAN_YEAR, period_start=start, period_end=end, bridge_received=False)
    assert g.days == days


def test_the_stamp_moves_with_any_input() -> None:
    a = soc_gap.gap(**PLAN_YEAR, **KEYSTONE, bridge_received=False).stamp.inputs_hash
    b = soc_gap.gap(**PLAN_YEAR, **KEYSTONE, bridge_received=True).stamp.inputs_hash
    assert a != b


def _report(*, days: int, bridged: bool, cuecs: tuple[str, ...]) -> sr.SocReport:
    g = soc_gap.Gap(None, None, days, bridged, soc_gap.Stamp("soc_gap", "1", "0" * 64))
    double = cast(Any, SimpleNamespace)  # Any: a CUEC test double
    rows = tuple(double(n=i + 1, status=s) for i, s in enumerate(cuecs))
    return sr.SocReport(cast(Any, SimpleNamespace()), g, (), rows)  # Any: test doubles and JSON


def test_ac7_2_reliance_waits_on_the_gap_then_on_cuec_evidence() -> None:
    assert isinstance(
        sr._blocking(_report(days=92, bridged=False, cuecs=("evidenced",))),  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        sr.GapOpen,
    )
    assert isinstance(
        sr._blocking(_report(days=92, bridged=True, cuecs=("evidence_missing",))),  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        sr.CuecEvidenceMissing,
    )
    assert sr._blocking(_report(days=92, bridged=True, cuecs=("evidenced", "evidenced"))) is None  # pyright: ignore[reportPrivateUsage] -- the private helper under test


def test_ac7_2_the_reliance_card_is_reserved_to_the_engagement_partner() -> None:
    from abacus.modules.review.slots import decision_kind

    sr.register_reliance_kind()
    kind = decision_kind(sr.RELIANCE_KIND)
    assert kind.reserved_role == "engagement_partner"
    assert sr._report_id(f"soc.{(rid := uuid4()).hex}") == rid  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert sr.GapOpen.code == "gap_open" and sr.CuecEvidenceMissing.code == "cuec_evidence_missing"
