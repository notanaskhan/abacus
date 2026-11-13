"""T-05-T32 (TASK-7622; T-05 F2, F7; DEC-4617): the workbook run's part-1 handlers. Ending capital
is computed by code (beginning + contributions - distributions + income share) and written with
its formula; the M-2 foots to the partners; a person's cell is never overwritten on a re-run;
K-1 shares come from the recipients' ownership notes; part-2 steps answer Needs attention."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.agents.api import RunStepFacts
from abacus.modules.tax import run_steps
from abacus.modules.tax.workbook_service import CellWrite

RETURN = uuid.uuid4()
FACTS = RunStepFacts(uuid.uuid4(), uuid.uuid4(), "capital_m2", 4, {"return_id": str(RETURN)})


class _Agent:
    tenant: Any = object()  # Any: a stand-in tenant


def _cells(rows: dict[str, str]) -> dict[str, dict[str, object]]:
    return {k: {"t": "decimal", "v": v} for k, v in rows.items()}


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[CellWrite]:
    out: list[CellWrite] = []

    async def write(
        agent: object, facts: object, return_id: object, writes: list[CellWrite]
    ) -> int:
        out.extend(writes)
        return len(writes)

    monkeypatch.setattr(run_steps, "_write", write)
    return out


def test_capital_m2_computes_ending_capital_and_foots_the_m2(
    written: list[CellWrite], monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = {
        2: ("Jonah Feld", "1000000", "0", "50000", "200000"),
        3: ("Pell Street II LLC", "3000000", "100000", "150000", "600000"),
    }
    values = _cells(
        {f"05!{col}{n}": v for n, row in rows.items() for col, v in zip("ABCDE", row, strict=True)}
    )

    async def current(
        tenant: object, target: str, target_id: object
    ) -> dict[str, dict[str, object]]:
        return values

    monkeypatch.setattr(run_steps, "current_values", current)
    result = asyncio.run(run_steps.capital_m2(_Agent(), FACTS))  # type: ignore[arg-type] -- a test double or the review api's own context alias
    assert result.state == "succeeded"
    by = {w.address: w for w in written}
    assert by["05!F2"].value == Decimal("1150000") and by["05!F2"].formula == "=B2+C2-D2+E2"
    assert by["05!F3"].value == Decimal("3550000")
    assert by["07!B9"].value == Decimal("4700000")


def test_capital_without_partner_rows_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def current(
        tenant: object, target: str, target_id: object
    ) -> dict[str, dict[str, object]]:
        return {}

    monkeypatch.setattr(run_steps, "current_values", current)
    result = asyncio.run(run_steps.capital_m2(_Agent(), FACTS))  # type: ignore[arg-type] -- a test double or the review api's own context alias
    assert (result.state, result.error_code) == ("failed", "capital_inputs_missing")


def test_a_human_cell_is_kept_on_a_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    async def sources(
        tenant: object, target: str, ids: list[object]
    ) -> dict[tuple[object, str], tuple[str, int]]:
        return {(RETURN, "05!F2"): ("human", 1), (RETURN, "05!F3"): ("formula", 0)}

    monkeypatch.setattr(run_steps, "latest_sources", sources)
    writes = [CellWrite("05!F2", Decimal(1), "formula"), CellWrite("05!F3", Decimal(2), "formula")]
    kept = asyncio.run(run_steps._kept(object(), RETURN, writes))  # type: ignore[arg-type] -- a test double or the review api's own context alias
    assert [w.address for w in kept] == ["05!F3"]


@pytest.mark.parametrize(
    ("note", "share"),
    [
        ("limited partner 25%", Decimal("0.25")),
        ("general partner 1.5 %", Decimal("0.015")),
        ("", None),
    ],
)
def test_k1_shares_come_from_the_ownership_note(note: str, share: Decimal | None) -> None:
    assert run_steps.share_of(note) == share


def test_every_part_two_step_has_its_handler() -> None:
    """T-05-T40 replaced S40's fail-closed stub with the part-2 handlers (DEC-4703)."""
    assert set(run_steps.PART_TWO_HANDLERS) == set(run_steps.PART_TWO)


@pytest.mark.parametrize("kind", ["depreciation_register", "bonus_eligibility"])
def test_a_report_step_with_no_report_needs_attention(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty workbook still answers Needs attention (`import_required`) and raises the
    step's issue, as S40's stub did."""
    issues: list[str] = []

    async def no_cells(tenant: object, target: object, return_id: object) -> dict[str, object]:
        return {}

    async def create_issue(*_args: object, **kwargs: object) -> object:
        issues.append(str(kwargs["source_ref"]))
        return object()

    import abacus.modules.review.api as review_api

    monkeypatch.setattr(run_steps, "current_values", no_cells)
    monkeypatch.setattr(review_api, "create_issue", create_issue)
    step = replace(FACTS, step_key=kind)
    handler = run_steps.PART_TWO_HANDLERS[kind]
    result = asyncio.run(handler(_Agent(), step))  # type: ignore[arg-type] -- a test double stands in for the run's context
    assert (result.state, result.error_code) == ("failed", "import_required")
    assert issues == [f"run_step:{kind}:import_required"]
