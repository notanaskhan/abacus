"""T-05-T27 (TASK-7519; T-05 F4; TXP-11; ADR-237): the workbook service. Cells are review fields
written through `record_value` by an engine (formula, engine import, TB link) or a person; a
formula is written back by the closed grammar and never evaluated as text; sheets project with
range paging; provenance names the formula's inputs; a citation to a superseded cell reads moved.

Row acceptance: "05 Capital!J12 provenance shows its writer, formula, inputs and the issue citing
it, and a citation to a superseded cell reads moved."
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.tax import workbook_service as wb


def _same_text(text: str) -> str:
    return text


@pytest.mark.parametrize(
    ("text", "key", "row", "col"),
    [
        ("05 Capital!J12", "05!J12", 12, 10),
        ("05!H12", "05!H12", 12, 8),
        ("06!C31", "06!C31", 31, 3),
    ],
)
def test_addresses_name_their_sheet(text: str, key: str, row: int, col: int) -> None:
    at = wb.address(text)
    assert (at.key, at.row, at.col, at.formula_key) == (key, row, col, f"{key}:f")


@pytest.mark.parametrize("text", ["J12", "05 Capital!", "5!J12", "05!J0", "=SUM(A1)"])
def test_a_bad_address_is_refused(text: str) -> None:
    with pytest.raises(wb.CellAddressInvalid):
        wb.address(text)


def test_the_1065_workbook_has_its_numbered_sheets() -> None:
    sheets = dict(wb.sheets_of("1065"))
    assert sheets["01"] == "01 Trial Balance"
    assert sheets["05"] == "05 Capital"
    assert sheets["06"] == "06 Schedule K"
    with pytest.raises(ValueError, match="two digits"):
        wb.register_sheets("1120s", [("1", "Bad")])


def test_projection_pages_by_range_and_carries_formulas() -> None:
    values: dict[str, dict[str, object]] = {
        "05!J12": {"t": "decimal", "v": "1550"},
        "05!J12:f": {"t": "text", "v": "=D12+E12+F12+G12+H12+I12"},
        "05!D12": {"t": "decimal", "v": "0"},
        "06!C31": {"t": "decimal", "v": "6200"},
    }
    cells, more = wb.sheet_cells(values, "05", "A1:J40")
    assert [c.address for c in cells] == ["D12", "J12"]
    assert cells[1].formula == "=D12+E12+F12+G12+H12+I12"
    assert more is None
    outside, _ = wb.sheet_cells(values, "05", "A1:E40")
    assert [c.address for c in outside] == ["D12"]


def test_projection_names_the_next_range_past_a_page() -> None:
    values = {f"01!A{r}": {"t": "decimal", "v": str(r)} for r in range(1, wb.PAGE + 6)}
    cells, more = wb.sheet_cells(values, "01", "A1:A999")
    assert len(cells) == wb.PAGE
    assert more == f"A{wb.PAGE + 1}:A999"


def test_inputs_are_the_formulas_references() -> None:
    assert wb.inputs_of("='06 Schedule K'!C31*25%") == ["06!C31"]
    assert wb.inputs_of("=F18+G18+H18") == ["F18", "G18", "H18"]
    assert wb.inputs_of(None) == []


def test_a_citation_to_a_superseded_cell_reads_moved() -> None:
    assert wb.citation_state(cited_version=2, current_version=3) == "moved"
    assert wb.citation_state(cited_version=3, current_version=3) == "current"


class _Tx:
    pass


def test_writes_go_through_record_value_with_the_engine_or_person_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, Any]] = []  # Any: record_value kwargs

    async def record(_tx: object, **kwargs: Any) -> int:  # noqa: ANN401 -- record_value stand-in
        seen.append(kwargs)
        return len(seen)

    monkeypatch.setattr(wb, "record_value", record)
    monkeypatch.setattr(wb, "checked_formula", _same_text)
    written = asyncio.run(
        wb.write_cells(
            _Tx(),  # type: ignore[arg-type] -- a unit of work stand-in
            engagement_id=uuid.uuid4(),
            return_id=uuid.uuid4(),
            writes=[
                wb.CellWrite("05!J12", Decimal(1550), "formula", formula="=SUM(D12:I12)"),
                wb.CellWrite("01!B4", "=HYPERLINK(evil)", "engine_import"),
                wb.CellWrite("05!H12", Decimal(1550), "human", citation_note="Harborline p. 1"),
            ],
        )
    )
    assert written == 3
    assert [(s["field_key"], s["value_source"]) for s in seen] == [
        ("05!J12", "formula"),
        ("05!J12:f", "formula"),
        ("01!B4", "engine_import"),
        ("05!H12", "human"),
    ]
    assert seen[2]["value"] == {"t": "text", "v": "=HYPERLINK(evil)"}  # a client string stays text
    assert {s["target_type"] for s in seen} == {wb.WORKBOOK}


def test_an_agent_source_or_a_formula_without_text_is_refused() -> None:
    for write in (
        wb.CellWrite("05!J12", Decimal(1), "agent_suggested"),  # type: ignore[arg-type] -- an invalid source under test
        wb.CellWrite("05!J12", Decimal(1), "formula"),
    ):
        with pytest.raises((wb.CellSourceInvalid, wb.FormulaInvalid)):
            asyncio.run(
                wb.write_cells(
                    _Tx(),  # type: ignore[arg-type] -- a unit of work stand-in
                    engagement_id=uuid.uuid4(),
                    return_id=uuid.uuid4(),
                    writes=[write],
                )
            )


def test_a_formula_outside_the_closed_grammar_is_422() -> None:
    with pytest.raises(wb.FormulaInvalid) as refused:
        wb.checked_formula("=EVAL(A1)")
    assert refused.value.code == "formula_invalid"
