"""A-09-T23: group scoping by code (Harlow & Pike FY2026)."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.assurance.compute import group_scoping as gs

# Each entity's contribution to consolidated assets after eliminations (A-09-T19's figures).
CONTRIBUTIONS = {
    "holdings": D("2600000"),
    "operating": D("0"),
    "manufacturing": D("27000000"),
    "distribution": D("12760000"),
    "real_estate": D("8400000"),
}
PLANNED: dict[str, gs.Planned] = {
    "holdings": "analytical_only",
    "operating": "analytical_only",
    "manufacturing": "full_scope",
    "distribution": "full_scope",
    "real_estate": "analytical_only",
}


def test_ac_the_decided_state_records_240_000_180_000_and_12_000() -> None:
    t = gs.thresholds(D("240000"))
    assert (t.materiality, t.pm, t.ct) == (D("240000.00"), D("180000.00"), D("12000.00"))


def test_ac_coverage_reads_78_and_22_percent_of_50_760_000() -> None:
    c = gs.coverage(CONTRIBUTIONS, PLANNED, D("50760000"))
    assert (c.covered_pct, c.not_covered_pct) == (D(78), D(22))
    assert c.covered + c.not_covered == D("50760000.00")


def test_ac_a_component_pm_at_or_above_180_000_answers_422() -> None:
    assert gs.validate_component_pm(D("135000"), D("180000")) == D("135000.00")
    with pytest.raises(gs.ComponentPmTooHigh):
        gs.validate_component_pm(D("180000"), D("180000"))
    assert gs.default_component_pm(D("180000"), D("53")) == D("135000.00")
