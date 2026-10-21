"""SPEC-311 (TASK-322): where the passed entries' aggregate falls against materiality (by code;
whether it is material stays the partner's judgement)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.fieldwork.misstatements import band_of

OVERALL, PM, CT = Decimal("252200"), Decimal("189200"), Decimal("12600")


@pytest.mark.parametrize(
    ("aggregate", "band"),
    [
        ("0", "clearly_trivial"),
        ("12600", "clearly_trivial"),
        ("12600.01", "below_performance"),
        ("189199.99", "below_performance"),
        ("189200", "below_overall"),
        ("252199.99", "below_overall"),
        ("252200", "above_overall"),
    ],
)
def test_ac4_bands(aggregate: str, band: str) -> None:
    assert band_of(Decimal(aggregate), OVERALL, PM, CT) == band
