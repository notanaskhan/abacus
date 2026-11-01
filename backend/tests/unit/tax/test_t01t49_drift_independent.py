"""T-01-T49 (TASK-2621; ADR-078; I-8879-DRIFT; DEC-85): independent tests for T-01-T36's drift rule
and the Pub 1345 tolerances it reads, from the contract and the golden cases alone.

- `filing.drift` relocks a figure that moved by strictly more than its tolerance (more than 50 on
  total income or AGI, more than 14 on tax, withholding, refund or balance due), or that appeared
  or disappeared; exactly the tolerance holds.
- The tolerances are read from C21's `form_8879_set` rows for the tax year, never a default: a
  year no row covers is `LookupError`.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml

from abacus.modules.platform import reference_sets
from abacus.modules.tax import filing

CASES = Path(__file__).parents[2] / "golden" / "tax" / "i8879_drift" / "cases.yaml"
GOLDEN = cast(dict[str, Any], yaml.safe_load(CASES.read_text()))  # Any: the YAML document
TOL = cast(dict[str, int], GOLDEN["tolerances"])


def test_the_goldens_carry_their_sign_off_references() -> None:
    assert set(GOLDEN["signed_off"]) == {"tax_cpa", "counsel"}


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=[c["name"] for c in GOLDEN["cases"]])
def test_i8879_drift(case: dict[str, Any]) -> None:  # Any: one YAML case
    moved = filing.drift(case["bound"], case["now"], TOL["income"], TOL["amounts"])
    assert moved == case["relock"]


def test_a_wider_tolerance_from_the_rows_holds_the_same_move() -> None:
    bound, now = {"US": {"agi": "245310"}}, {"US": {"agi": "245390"}}
    assert filing.drift(bound, now, 50, 14) == ["US.agi"]
    assert filing.drift(bound, now, 100, 14) == []


async def test_tolerances_are_the_form_set_rows_for_the_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = uuid.uuid4()
    payload = SimpleNamespace(
        rows=[SimpleNamespace(tax_year=2025)],
        tolerances=SimpleNamespace(
            total_income_or_agi_usd=50, tax_withholding_refund_balance_usd=14
        ),
    )

    async def in_effect(kind: str, as_of: date) -> list[SimpleNamespace]:
        assert kind == "form_8879_set"
        return [SimpleNamespace(payload=payload, version_id=version)]

    monkeypatch.setattr(reference_sets, "references_in_effect", in_effect)
    found = await reference_sets.pub1345_tolerances(2025, as_of=date(2026, 9, 1))
    assert (
        found.total_income_or_agi_usd,
        found.tax_withholding_refund_balance_usd,
        found.reference_set_version_id,
    ) == (50, 14, version)
    with pytest.raises(LookupError):
        await reference_sets.pub1345_tolerances(2026, as_of=date(2026, 9, 1))
