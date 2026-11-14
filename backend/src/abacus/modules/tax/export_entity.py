"""The entity section of the engine export (T-05-T60; T-05 F11;
`docs/contracts/tax-engine-bridge.md` §6; ADR-150 W2 `tax_engine_file_bridge`, ADR P-18; DEC-49,
DEC-77, DEC-78; DEC-4931). RED: what leaves the firm for the engine.

An entity return (Form 1065) exports through T-01's file bridge (`export.export_return`, a
person's, after the signer's final approval, consuming that approval's grant) with two more sheets
built by code from the **approved checkpoint only** (the workbook as it stood when that checkpoint
was recorded, `review.api.values_as_of`, never a later edit):

- `TTB`: the tax trial balance by CCH line code (`cch_line_code`, `label`, `amount`), from sheet
  03 Form Lines. The CCH line code is the 1065 form-line key the workbook already carries; the
  pilot firm's own Axcess validates that layout in shadow (T-05 OQ-1, R-05).
- `Allocations`: each partner's share of each Schedule K line (`partner_ref`, `partner`,
  `schedule_k_line`, `amount`), from sheet 06's lines and sheet 09's partner columns.

**Blocked while Unmapped > 0** (409 `export_unmapped`): every account of the newest trial balance
must carry a form line before anything leaves, checked before the approval's grant is spent.
**Never transmit** (R-04): nothing here sends, files or calls the engine; the file is carried by a
person, and only a person marks it exported (`export.mark_exported`) or records a transmission.

Values are TRI: never logged, never in an error's facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.modules.review.api import checkpoint_recorded_at, values_as_of
from abacus.modules.tax.entity_gates import engagement_of_return, unmapped_accounts
from abacus.modules.tax.entity_schedules import Values, dec, partner_id_for, recipients
from abacus.modules.tax.workbook_service import WORKBOOK

ENTITY_FORMS: Final = frozenset({"1065"})
TTB_HEADER: Final = ("cch_line_code", "label", "amount")
ALLOCATION_HEADER: Final = ("partner_ref", "partner", "schedule_k_line", "amount")


class ExportUnmapped(DomainConflict):
    """An account of the newest trial balance has no form line, or there is no trial balance."""

    code = "export_unmapped"


@dataclass(frozen=True)
class TtbLine:
    cch_line_code: str
    label: str
    amount: Decimal


@dataclass(frozen=True)
class Allocation:
    partner_ref: UUID
    partner: str
    schedule_k_line: str
    amount: Decimal


@dataclass(frozen=True)
class EntitySection:
    ttb: tuple[TtbLine, ...]
    allocations: tuple[Allocation, ...]


def _text(values: Values, key: str) -> str:
    cell = values.get(key)
    value = None if cell is None else cell.get("v")
    return "" if value is None else str(value).strip()


def _rows(values: Values, sheet: str) -> list[int]:
    """The data rows of a sheet (row 1 is its header), in order, while column A holds a value."""
    out: list[int] = []
    n = 2
    while f"{sheet}!A{n}" in values:
        if _text(values, f"{sheet}!A{n}") not in ("", "Total"):
            out.append(n)
        n += 1
    return out


def ttb_lines(values: Values) -> list[TtbLine]:
    """Sheet 03: A the form line key (the CCH line code), B its label, C the net amount."""
    return [
        TtbLine(_text(values, f"03!A{n}"), _text(values, f"03!B{n}"), dec(values, f"03!C{n}"))
        for n in _rows(values, "03")
    ]


def allocations(values: Values, return_id: UUID, known: Mapping[str, UUID]) -> list[Allocation]:
    """Sheet 06's Schedule K lines (A the line) by sheet 09's partner columns (row 1 the partner,
    the line's row its share). A partner with no recipient yet keeps a stable derived id."""
    partners: list[tuple[str, str]] = []
    col = "B"
    while f"09!{col}1" in values:
        name = _text(values, f"09!{col}1")
        if name:
            partners.append((col, name))
        col = chr(ord(col) + 1)
    out: list[Allocation] = []
    for n in _rows(values, "06"):
        line = _text(values, f"06!A{n}")
        for column, name in partners:
            out.append(
                Allocation(
                    partner_id_for(return_id, name, known), name, line,
                    dec(values, f"09!{column}{n}"),
                )
            )  # fmt: skip
    return out


async def require_mapped(tenant: TenantContext, return_id: UUID) -> None:
    """F11: no export while any account of the newest trial balance is unmapped."""
    engagement_id = await engagement_of_return(tenant, return_id)
    unmapped = None if engagement_id is None else await unmapped_accounts(tenant, engagement_id)
    if unmapped is None or unmapped > 0:
        raise ExportUnmapped(facts={"work_item_id": str(return_id)})


async def entity_section(
    tenant: TenantContext, return_id: UUID, checkpoint_id: UUID
) -> EntitySection:
    """The two sheets, from the workbook as the approved checkpoint covered it."""
    at = await checkpoint_recorded_at(tenant, checkpoint_id)
    values = (await values_as_of(tenant, WORKBOOK, [return_id], at)).get(return_id, {})
    known = {name: rid for rid, name in await recipients(tenant, return_id)}
    return EntitySection(tuple(ttb_lines(values)), tuple(allocations(values, return_id, known)))


__all__ = [
    "ALLOCATION_HEADER",
    "ENTITY_FORMS",
    "TTB_HEADER",
    "Allocation",
    "EntitySection",
    "ExportUnmapped",
    "TtbLine",
    "allocations",
    "entity_section",
    "require_mapped",
    "ttb_lines",
]
