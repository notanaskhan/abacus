"""A person's edit of one workbook cell (T-05-T35; T-05 F4; TXP-11; ADR-237, ADR-050; DEC-4620).
Amber: writes go through `workbook_service.write_cells` (review's insert-only versions) in one unit
of work, and the edit is checkpointed through P-04.

- **Who.** The route authorised `workbook.edit` on the return. A person holding the `preparer`
  function on the return's work item edits the cell; a person holding only a reviewer function
  proposes it instead: a review note anchored on the cell carries the proposed value or formula,
  and the cell does not change (a reviewer never overwrites the preparer's figure; TXP-11's
  "Proposed" pill). Neither function: 403 `preparer_function_required`.
- **Versions.** `expected_version` is the cell's latest version number (0 for a cell never
  written); any other number is 409 `cell_version_conflict`. A run open on the return holds the
  cells: 409 `cells_locked_by_run`.
- **Formulas.** Parsed by the closed grammar (ADR-237), never evaluated as text; outside it, or a
  cycle the edit would make, is 422 `formula_invalid`.
- **Recompute.** Bounded and synchronous: the edited cell's dependents (transitively, at most
  `MAX_RECOMPUTE`), in the DAG's order, written as `formula` versions in the same unit of work. A
  larger fan-out is 422 `recompute_too_large`: the person starts a run instead.
- **Checkpoint.** After the write, a person's saved checkpoint named
  "Edited 05 Capital!H12 by Olivia Brandt". Sign-offs whose content hash covered the old figures go
  stale through review's own stale detection (the workbook's content hash moved).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import functions_on
from abacus.modules.identity.api import AuthContext, display_names
from abacus.modules.review.api import (
    current_values,
    field_timeline,
    raise_review_note,
    save_checkpoint,
)
from abacus.modules.tax.workbook_service import (
    WORKBOOK,
    Address,
    CellWrite,
    FormulaInvalid,
    address,
    checked_formula,
    sheets_of,
    write_cells,
)
from abacus.modules.workpapers.api import (
    FormulaCellInput,
    FormulaCycleError,
    FormulaError,
    FormulaWorkbook,
    build_formula_graph,
    canonical_address,
    dirty_cells,
    evaluate_workbook,
)

MAX_RECOMPUTE: Final = 500
PREPARER: Final = "preparer"


class CellVersionConflict(DomainConflict):
    """The cell moved since the person read it (TXP-11's 409 path: reload and re-apply)."""

    code = "cell_version_conflict"


class CellsLockedByRun(DomainConflict):
    """A workbook run is open on the return; its cells are held until it ends."""

    code = "cells_locked_by_run"


class PreparerFunctionRequired(DomainForbidden):
    """Neither the preparer nor a reviewer function on the return's work item."""

    code = "preparer_function_required"


class RecomputeTooLarge(DomainInvalid):
    """The edit's dependents exceed the synchronous bound; a run recomputes them."""

    code = "recompute_too_large"


@dataclass(frozen=True)
class EditOutcome:
    address: str  # "05!H12"
    value: str | None
    formula: str | None
    version: int
    recomputed: tuple[str, ...] = ()
    proposal_note_id: UUID | None = None
    checkpoint_id: UUID | None = None


# --- pure parts ----------------------------------------------------------------------------------


def _dag_key(field_key: str) -> str:
    sheet, _, a1 = field_key.partition("!")
    return canonical_address(sheet, a1)


def _field_key(dag_key: str) -> str:
    sheet, _, a1 = dag_key.rpartition("!")
    return f"{sheet.strip("'").replace("''", "'")}!{a1}"


def _number(raw: object) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def book_of(form: str, values: Mapping[str, Mapping[str, object]]) -> FormulaWorkbook:
    """The workbook's cells as the DAG reads them: a formula where `key:f` holds one, else the
    value (text reads as no number)."""
    book = FormulaWorkbook(tuple(n for n, _ in sheets_of(form)))
    for key, cell in values.items():
        if key.endswith(":f"):
            continue
        sheet, _, a1 = key.partition("!")
        if sheet not in book.sheets:
            continue
        formula = values.get(f"{key}:f", {}).get("v")
        if formula:
            book.set(sheet, a1, FormulaCellInput(formula=str(formula)))
        else:
            book.set(sheet, a1, FormulaCellInput(value=_number(cell.get("v"))))
    return book


def apply_edit(
    book: FormulaWorkbook, at: Address, value: Decimal | None, formula: str | None
) -> tuple[dict[str, Decimal | None], tuple[str, ...]]:
    """The edited cell and its dependents' new values (by field key), and the dependents in
    order. A cycle or a parse failure is `formula_invalid`; too many dependents, too large."""
    edited = book.set(at.sheet, at.a1, FormulaCellInput(value=value, formula=formula))
    try:
        graph = build_formula_graph(book)
    except FormulaCycleError:
        raise FormulaInvalid(facts={"code": "cycle"}) from None
    except FormulaError as error:
        raise FormulaInvalid(facts={"code": str(getattr(error, "code", "syntax"))}) from None
    touched = dirty_cells(graph, [edited])
    if len(touched) > MAX_RECOMPUTE:
        raise RecomputeTooLarge(facts={"cells": len(touched)})
    results = evaluate_workbook(book, graph)
    out: dict[str, Decimal | None] = {}
    if formula is not None:
        out[at.key] = results[edited].value
    else:
        out[at.key] = value
    for dependent in touched:
        out[_field_key(dependent)] = results[dependent].value
    return out, tuple(_field_key(d) for d in touched)


def checkpoint_name(form: str, at: Address, person: str) -> str:
    titles = dict(sheets_of(form))
    return f"Edited {titles.get(at.sheet, at.sheet)}!{at.a1} by {person}"


# --- the edit ------------------------------------------------------------------------------------


async def _version(ctx: AuthContext, return_id: UUID, key: str) -> int:
    timeline = await field_timeline(ctx.tenant, WORKBOOK, return_id, key)
    return timeline[-1].seq if timeline else 0


async def edit_cell(
    ctx: AuthContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    form: str,
    address_text: str,
    expected_version: int,
    value: str | None,
    formula: str | None,
    run_open: bool,
) -> EditOutcome:
    """The route authorised `workbook.edit` on the return and checked the flag."""
    at = address(address_text)
    if at.sheet not in {n for n, _ in sheets_of(form)}:
        raise FormulaInvalid(facts={"code": "ref_invalid"})
    if (value is None) == (formula is None):
        raise FormulaInvalid(facts={"code": "value_or_formula"})
    rendered = None if formula is None else checked_formula(formula)
    number = None if value is None else _number(value)
    if value is not None and number is None and value.strip().startswith("="):
        raise FormulaInvalid(facts={"code": "syntax"})  # a formula typed as a value
    if run_open:
        raise CellsLockedByRun(facts={"return_id": str(return_id)})
    current = await _version(ctx, return_id, at.key)
    if expected_version != current:
        raise CellVersionConflict(facts={"current_version": current})

    held = await functions_on(ctx.tenant, return_id, ctx.user_id)
    if PREPARER not in held:
        if not held:
            raise PreparerFunctionRequired(facts={"return_id": str(return_id)})
        proposed = rendered if rendered is not None else value
        note = await raise_review_note(
            ctx,
            WORKBOOK,
            return_id,
            anchor_kind="cell",
            anchor_ref=at.key,
            body=f"Proposed {at.key}: {proposed}",
            assignee=None,
        )
        return EditOutcome(
            address=at.key,
            value=None,
            formula=None,
            version=current,
            proposal_note_id=note.note.id,
        )

    values = await current_values(ctx.tenant, WORKBOOK, return_id)
    book = book_of(form, values)
    figures, touched = apply_edit(book, at, number, rendered)
    person = (await display_names([ctx.user_id])).get(ctx.user_id, "A person")
    name = checkpoint_name(form, at, person)
    writes = [
        CellWrite(
            at.key,
            figures[at.key] if rendered is not None or number is not None else value,
            "human",
            formula=rendered,
            citation_note=name,
        )
    ]
    for key in touched:
        dependent_formula = values.get(f"{key}:f", {}).get("v")
        writes.append(
            CellWrite(
                key,
                figures[key],
                "formula",
                formula=None if dependent_formula is None else str(dependent_formula),
            )
        )
    async with uow(ctx.tenant) as tx:
        await write_cells(tx, engagement_id=engagement_id, return_id=return_id, writes=writes)
        tx.record(
            "workbook.cell_edited",
            target=Target(WORKBOOK, return_id),
            after=Ref(cell=at.key, recomputed=len(touched)),
        )
    checkpoint = await save_checkpoint(ctx, WORKBOOK, return_id, name)
    shown = figures[at.key]
    if rendered is None and number is None:
        shown_text = value  # a text cell keeps its text
    else:
        shown_text = None if shown is None else format(shown, "f")
    return EditOutcome(
        address=at.key,
        value=shown_text,
        formula=rendered,
        version=await _version(ctx, return_id, at.key),
        recomputed=touched,
        checkpoint_id=checkpoint.id,
    )


__all__ = [
    "MAX_RECOMPUTE",
    "CellVersionConflict",
    "CellsLockedByRun",
    "EditOutcome",
    "PreparerFunctionRequired",
    "RecomputeTooLarge",
    "apply_edit",
    "book_of",
    "checkpoint_name",
    "edit_cell",
]
