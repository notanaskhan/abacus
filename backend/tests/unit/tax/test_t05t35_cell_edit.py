"""T-05-T35 (TASK-7625; DEC-4620): the cell edit's pure parts and its refusals.

Olivia's edit of 05!H12 recomputes J12 and J13 (the dependents, in order) and names the
checkpoint; a cycle or a formula outside the grammar is `formula_invalid`; the fan-out is bounded.
The service paths (preparer edit, reviewer proposal, 409s) run against the database in
T-05-T56's independent suite and the S40 end pass.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax import cell_edit
from abacus.modules.tax.workbook_service import FormulaInvalid, address

D = Decimal


VALUES = {
    "05!H12": {"t": "decimal", "v": "100"},
    "05!I12": {"t": "decimal", "v": "20"},
    "05!J12": {"t": "decimal", "v": "120"},
    "05!J12:f": {"t": "text", "v": "=H12+I12"},
    "05!J13": {"t": "decimal", "v": "120"},
    "05!J13:f": {"t": "text", "v": "=SUM(J12:J12)"},
    "07!B9": {"t": "decimal", "v": "5"},
}


def test_ac_an_edit_recomputes_its_dependents_in_order() -> None:
    book = cell_edit.book_of("1065", VALUES)
    figures, touched = cell_edit.apply_edit(book, address("05!H12"), D("124"), None)
    assert touched == ("05!J12", "05!J13")
    assert figures == {"05!H12": D("124"), "05!J12": D("144"), "05!J13": D("144")}


def test_ac_an_unrelated_cell_is_not_recomputed() -> None:
    book = cell_edit.book_of("1065", VALUES)
    _figures, touched = cell_edit.apply_edit(book, address("07!B9"), D("6"), None)
    assert touched == ()


def test_ac_a_formula_edit_is_evaluated_by_code() -> None:
    book = cell_edit.book_of("1065", VALUES)
    figures, touched = cell_edit.apply_edit(book, address("05!H12"), None, "=I12*2")
    assert figures["05!H12"] == D("40") and figures["05!J12"] == D("60")
    assert touched == ("05!J12", "05!J13")


def test_ac_a_cycle_is_formula_invalid() -> None:
    book = cell_edit.book_of("1065", VALUES)
    with pytest.raises(FormulaInvalid):
        cell_edit.apply_edit(book, address("05!H12"), None, "=J13")


def test_ac_the_recompute_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cell_edit, "MAX_RECOMPUTE", 1)
    book = cell_edit.book_of("1065", VALUES)
    with pytest.raises(cell_edit.RecomputeTooLarge):
        cell_edit.apply_edit(book, address("05!H12"), D("1"), None)


def test_ac_the_checkpoint_names_the_sheet_cell_and_person() -> None:
    name = cell_edit.checkpoint_name("1065", address("05!H12"), "Olivia Brandt")
    assert name == "Edited 05 Capital!H12 by Olivia Brandt"


def test_ac_text_cells_read_as_no_number() -> None:
    book = cell_edit.book_of("1065", {**VALUES, "05!A12": {"t": "text", "v": "Pell Street"}})
    assert book.cells["'05'!A12"].value is None


def test_ac_the_service_refuses_value_and_formula_together() -> None:
    import asyncio
    import uuid

    with pytest.raises(FormulaInvalid):
        asyncio.run(
            cell_edit.edit_cell(
                None,  # type: ignore[arg-type]  # refused before any read
                return_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                form="1065",
                address_text="05!H12",
                expected_version=1,
                value="1",
                formula="=1",
                run_open=False,
            )
        )


def test_ac_an_open_run_locks_the_cells() -> None:
    import asyncio
    import uuid

    with pytest.raises(cell_edit.CellsLockedByRun):
        asyncio.run(
            cell_edit.edit_cell(
                None,  # type: ignore[arg-type]  # refused before any read
                return_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                form="1065",
                address_text="05!H12",
                expected_version=1,
                value="1",
                formula=None,
                run_open=True,
            )
        )
