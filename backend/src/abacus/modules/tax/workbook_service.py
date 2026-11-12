"""The entity return's numbered workbook: cells, sheets and provenance (T-05-T27; T-05 F4; TXP-11;
ADR-237, ADR-050; DEC-4403, DEC-4519). Amber: every write goes through `review.api.record_value`.

- **One store.** A cell is a review field on the return's workbook (`tax_workbook` target, the
  return's work item): field key `05!J12` holds its value (`{t, v}`), and a formula cell also
  holds `05!J12:f`, its formula as written back by the closed grammar (ADR-237: parsed, never
  evaluated as text). Versions are review's insert-only `field_value_versions`, so each cell has a
  history, a writer and its citations, and SHL-09 reads it like any field.
- **Who writes.** Engines write `formula`, `engine_import` or `tb_linked` values (code computes,
  ADR-050); a person writes `human` with a citation note (record_value's rule). Nothing else: an
  agent never writes a cell (it proposes, DEC-84).
- **Sheets.** The form's sheets in order (Form 1065: 01 Trial Balance … 09 K-1s); a projection
  reads one sheet with range paging (`A1:J40`, 400 cells a page) and names the next range.
- **Provenance.** A cell's writer, formula, inputs (the formula's references), citations and the
  issues citing it; a citation to a version older than the current one reads `moved`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.review.api import record_value
from abacus.modules.workpapers.api import FormulaError, parse_formula, render_formula

WORKBOOK: Final = "tax_workbook"
CellSource = Literal["formula", "engine_import", "tb_linked", "human"]
SOURCES: Final = frozenset({"formula", "engine_import", "tb_linked", "human"})
PAGE: Final = 400
# Form 1065's workbook (T-05 §2.2, F4): sheet number → title, in order.
SHEETS_1065: Final[tuple[tuple[str, str], ...]] = (
    ("01", "01 Trial Balance"),
    ("02", "02 Adjustments"),
    ("03", "03 Form Lines"),
    ("04", "04 Allocation"),
    ("05", "05 Capital"),
    ("06", "06 Schedule K"),
    ("07", "07 M-2"),
    ("08", "08 State"),
    ("09", "09 K-1s"),
)
_SHEETS: dict[str, tuple[tuple[str, str], ...]] = {"1065": SHEETS_1065}
_ADDRESS = re.compile(r"^(?:(\d{2})(?: [A-Za-z0-9 &'.-]{1,40})?!)?([A-Z]{1,3})([1-9][0-9]{0,5})$")
_RANGE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]{0,5}):([A-Z]{1,3})([1-9][0-9]{0,5})$")


def engine_may_write(current_source: str | None) -> bool:
    """T-05-T31 (DEC-4616): a run step writes a cell only where no person wrote the current value:
    a re-run keeps every human-edited cell (`keep_human`)."""
    return current_source != "human"


class CellAddressInvalid(DomainInvalid):
    """The address is not `<sheet>!<column><row>` on one of the form's sheets."""

    code = "cell_address_invalid"


class CellSourceInvalid(DomainInvalid):
    """Written by an engine (formula, engine import, TB link) or by a person, nothing else."""

    code = "cell_source_invalid"


class FormulaInvalid(DomainInvalid):
    """The formula does not parse in the workpapers grammar (no code is evaluated)."""

    code = "formula_invalid"


def register_sheets(form: str, sheets: Sequence[tuple[str, str]]) -> None:
    """Another form's workbook (1120-S, 1041) registers its sheets the same way."""
    numbers = [n for n, _ in sheets]
    if len(set(numbers)) != len(numbers) or not all(re.fullmatch(r"\d{2}", n) for n in numbers):
        raise ValueError("sheet numbers are two digits, once each")
    _SHEETS[form] = tuple(sheets)


def sheets_of(form: str) -> tuple[tuple[str, str], ...]:
    return _SHEETS.get(form, ())


def _col(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


@dataclass(frozen=True, order=True)
class Address:
    sheet: str  # "05"
    row: int
    col: int
    a1: str  # "J12"

    @property
    def key(self) -> str:
        return f"{self.sheet}!{self.a1}"

    @property
    def formula_key(self) -> str:
        return f"{self.key}:f"


def address(text: str, default_sheet: str | None = None) -> Address:
    """`05 Capital!J12`, `05!J12` or (with a default sheet) `J12`."""
    m = _ADDRESS.fullmatch(text.strip())
    if m is None:
        raise CellAddressInvalid(facts={"field": "address"})
    sheet = m.group(1) or default_sheet
    if sheet is None:
        raise CellAddressInvalid(facts={"field": "address"})
    letters, row = m.group(2), int(m.group(3))
    return Address(sheet, row, _col(letters), f"{letters}{row}")


@dataclass(frozen=True)
class CellWrite:
    address: str
    value: Decimal | str | None
    source: CellSource
    formula: str | None = None
    citation_ids: tuple[UUID, ...] = ()
    citation_note: str | None = None


def _typed(value: Decimal | str | None) -> dict[str, object]:
    if value is None:
        return {"t": "decimal", "v": None}
    if isinstance(value, Decimal):
        return {"t": "decimal", "v": format(value, "f")}
    return {"t": "text", "v": value}  # client strings stay text, even when they start with "="


def checked_formula(text: str) -> str:
    """The formula as the closed grammar writes it back; 422 `formula_invalid` outside it."""
    try:
        return render_formula(parse_formula(text))
    except FormulaError as error:
        raise FormulaInvalid(facts={"code": str(getattr(error, "code", "syntax"))}) from None


async def write_cells(
    tx: UnitOfWork,
    *,
    engagement_id: UUID,
    return_id: UUID,
    writes: Sequence[CellWrite],
    on_behalf_of_user_id: UUID | None = None,
) -> int:
    """Each cell's next version through `record_value`, in the caller's unit of work (the caller
    authorised `workbook.edit` or runs a workbook step). Returns the cells written."""
    written = 0
    for w in writes:
        if w.source not in SOURCES:
            raise CellSourceInvalid(facts={"source": str(w.source)})
        at = address(w.address)
        if w.source == "formula" and not w.formula:
            raise FormulaInvalid(facts={"code": "missing"})
        cause = (
            "edit"
            if w.source == "human"
            else ("import" if w.source == "engine_import" else "recompute")
        )
        await record_value(
            tx,
            engagement_id=engagement_id,
            target_type=WORKBOOK,
            target_id=return_id,
            field_key=at.key,
            value=_typed(w.value),
            value_source=w.source,
            cause=cause,
            on_behalf_of_user_id=on_behalf_of_user_id,
            citation_ids=w.citation_ids,
            citation_note=w.citation_note,
        )
        if w.formula:
            await record_value(
                tx,
                engagement_id=engagement_id,
                target_type=WORKBOOK,
                target_id=return_id,
                field_key=at.formula_key,
                value={"t": "text", "v": checked_formula(w.formula)},
                value_source="formula",
                cause="recompute",
            )
        written += 1
    return written


@dataclass(frozen=True)
class SheetCell:
    address: str  # "J12"
    value: str | None
    formula: str | None


def sheet_cells(
    values: Mapping[str, Mapping[str, object]], sheet: str, range_: str | None = None
) -> tuple[list[SheetCell], str | None]:
    """One sheet's cells in row then column order, within `range_` (`A1:J40`), at most `PAGE`;
    the next range (the rows after this page in the same columns) when more remain."""
    lo_col, lo_row, hi_col, hi_row = 1, 1, 18278, 999999
    if range_ is not None:
        m = _RANGE.fullmatch(range_)
        if m is None:
            raise CellAddressInvalid(facts={"field": "range"})
        lo_col, lo_row = _col(m.group(1)), int(m.group(2))
        hi_col, hi_row = _col(m.group(3)), int(m.group(4))
    found: list[tuple[Address, SheetCell]] = []
    for key, value in values.items():
        if key.endswith(":f") or not key.startswith(f"{sheet}!"):
            continue
        at = address(key)
        if not (lo_row <= at.row <= hi_row and lo_col <= at.col <= hi_col):
            continue
        formula = values.get(at.formula_key, {}).get("v")
        raw = value.get("v")
        found.append(
            (
                at,
                SheetCell(
                    at.a1,
                    None if raw is None else str(raw),
                    None if formula is None else str(formula),
                ),
            )
        )
    found.sort(key=lambda pair: (pair[0].row, pair[0].col))
    page = [cell for _, cell in found[:PAGE]]
    if len(found) <= PAGE:
        return page, None
    next_row = found[PAGE][0].row
    first = range_.split(":")[0] if range_ else "A1"
    last = range_.split(":")[1] if range_ else "ZZZ999999"
    letters_lo = re.sub(r"\d", "", first)
    letters_hi = re.sub(r"\d", "", last)
    return page, f"{letters_lo}{next_row}:{letters_hi}{re.sub(r'[A-Z]', '', last)}"


def inputs_of(formula: str | None) -> list[str]:
    """The cells a formula reads, as written (`05!H12`, `06!C31`), for the provenance panel."""
    if not formula:
        return []
    refs = re.findall(r"(?:'?(\d{2})[^'!]*'?!)?\$?([A-Z]{1,3})\$?([1-9][0-9]{0,5})", formula)
    return [f"{s}!{c}{r}" if s else f"{c}{r}" for s, c, r in refs]


def citation_state(cited_version: int, current_version: int) -> Literal["current", "moved"]:
    """A citation to a superseded cell reads `moved` (the figure it pointed at changed)."""
    return "current" if cited_version >= current_version else "moved"


def sheet_or_404(form: str, sheet: str) -> str:
    if sheet not in {n for n, _ in sheets_of(form)}:
        raise NotFound("workbook_sheet")
    return sheet


# --- the review registrations (field owner, facts) and the reads behind TXP-11 -----------------


async def workbook_facts(tenant: object, return_id: UUID) -> object:
    """The workbook as a reviewable (SHL-09's provenance and ticks read it through review)."""
    import hashlib
    import json

    from sqlalchemy import text

    from abacus.kernel.db import tenant_session
    from abacus.modules.review.api import ReviewableFacts, current_values

    async with tenant_session(tenant) as session:  # type: ignore[arg-type] -- the review api takes its own TenantContext alias
        engagement = await session.scalar(
            text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r"),
            {"r": return_id},
        )
    if engagement is None:
        raise NotFound(WORKBOOK)
    values = await current_values(tenant, WORKBOOK, return_id)  # type: ignore[arg-type] -- the review api takes its own TenantContext alias
    digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return ReviewableFacts(
        target_type=WORKBOOK,
        target_id=return_id,
        engagement_id=UUID(str(engagement)),
        content_hash=f"sha256:{digest}",
        version_no=max(1, len(values)),
        preparer_user_ids=frozenset(),
    )


async def cell_value(tenant: object, return_id: UUID, field_key: str) -> dict[str, object] | None:
    from abacus.modules.review.api import current_values

    values = await current_values(tenant, WORKBOOK, return_id)  # type: ignore[arg-type] -- the review api takes its own TenantContext alias
    found = values.get(field_key)
    return None if found is None else dict(found)


def register() -> None:
    """At the tax api's import: the workbook's cells are review fields (TRI, C19)."""
    from abacus.modules.review.api import (
        FieldOwner,
        register_field_owner,
        register_reviewable_facts,
    )

    register_field_owner(
        FieldOwner(WORKBOOK, cell_value, frozenset({"*"}), label_of=lambda key: key)  # type: ignore[arg-type] -- the owner registry is typed for review-owned values
    )
    register_reviewable_facts(WORKBOOK, workbook_facts)  # type: ignore[arg-type] -- the facts registry is typed for review-owned values
