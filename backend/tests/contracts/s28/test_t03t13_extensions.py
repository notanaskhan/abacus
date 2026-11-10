"""T-03-T13 (TASK-3331): goldens and properties for extensions, from the row: "Golden YAML
files carry
source and reviewed_by fields, pass on exact Decimal and date equality, and tallies recompute from
visible rows only." `counts` takes only the rows it is given, so a walled return can't reach a
tally.
The TY2027 calendar cases need T-03-T07's estimate schedules (S27 partial) and are recorded there.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.tax.compute.payments import (
    _pct,  # pyright: ignore[reportPrivateUsage] -- the rounding rule
)
from abacus.modules.tax.extensions import counts

GOLDEN = cast(
    dict[str, Any],  # Any: YAML
    yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "golden/tax/tax13_safe_harbor.yaml").read_text()
    ),
)


def test_ac_the_golden_names_its_source_and_review() -> None:
    assert GOLDEN["source"]
    assert "reviewed_by" in GOLDEN


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: str(c["name"]))
def test_ac_the_target_is_exact(case: dict[str, str]) -> None:
    assert _pct(Decimal(case["projected"]), Decimal(case["pct"]), 2) == Decimal(case["target"])


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: str(c["name"]))
def test_ac_each_row_meets_its_target(case: dict[str, str]) -> None:
    assert Decimal(case["paid"]) >= Decimal(case["target"])


@given(
    st.decimals(min_value=0, max_value=10_000_000, places=2, allow_nan=False, allow_infinity=False)
)
def test_ac_a_ninety_percent_target_never_exceeds_the_liability(projected: Decimal) -> None:
    assert _pct(projected, Decimal(90), 2) <= projected


def test_ac_counts_are_over_the_rows_given_only() -> None:
    assert sum(counts([]).values()) == 0
