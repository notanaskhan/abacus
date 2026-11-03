"""A-04-T29 (TASK-3220; DEC-2220): mode `ic` and code's materiality comparison.

Row acceptance (part): "row 3's 48,600 is compared by code to 189,150 and 12,610". The mode has
its own prompt on spec v9; the comparison and its narration are code's (AC6.5).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import pytest

from abacus.modules.agents.specs import _specs
from abacus.modules.assurance import ic_mode

D = Decimal


def test_row_3_is_compared_by_code() -> None:
    found = ic_mode.compare(D("48600"), D("189150"), D("12610"))
    assert found.position == "between"
    assert found.narration == "48,600 below PM 189,150 and above CT 12,610"
    assert "$" not in found.narration


@pytest.mark.parametrize(
    ("amount", "position"),
    [("200000", "above_pm"), ("12610", "below_ct"), ("-48600", "between")],
)
def test_positions(amount: str, position: str) -> None:
    assert ic_mode.compare(D(amount), D("189150"), D("12610")).position == position


def test_facts_name_the_rows_and_the_thresholds() -> None:
    facts: dict[str, Any] = dict(  # Any: fact values are JSON objects of mixed shape
        ic_mode.comparison_facts(D("189150"), D("12610"), [(3, D("48600"))])
    )
    assert facts["performance_materiality"] == {"t": "decimal", "v": "189150"}
    assert facts["row_3_compared_to_materiality"]["v"].startswith("48,600 below PM")


def test_the_mode_has_its_own_prompt() -> None:
    spec = cast("dict[str, Any]", _specs.SPECS["workpapers.section_drafter"])
    assert spec["version"] == 9
    assert spec["modes"]["ic"]["prompt"] == "workpapers.section_draft.ic@v1"
