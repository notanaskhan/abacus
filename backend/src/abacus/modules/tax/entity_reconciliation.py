"""Reconciliation to the engine of record (T-05-T61; T-05 F11; DEC-77, DEC-78; ADR-050; DEC-4934).

An entity return's figures that the engine owns are compared, by code, with the workbook once a
person approves a CCH import checkpoint:

- **Schedule K totals**: engine key `schedule_k.<line>` against sheet 06 (A the line, C the
  total);
- **each partner's K-1 boxes**: `k1.<partner_ref>.<line>` against sheet 09's partner column;
- **ending capital**: `capital.<partner_ref>.ending` against sheet 05 F;
- **M-2**: `m2.<n>` against sheet 07 as drafted (lines 1–9, footed by code).

`partner_ref` is the id the export's `Allocations` sheet carried (`export_entity.allocations`), so
an import names the same partner. The engine's figures are the values its approved import wrote
on the return (`value_source = engine_import`); nothing is compared before a person approves.

Each difference raises one `engine_diagnostic` issue, deduplicated by `(work item, source_ref)`
with `source_ref = recon:<key>`, blocking final approval; its title names the line, never a figure
(figures are TRI). A matching import reports 0 unexplained differences. Accrued's figures that
the engine owns are labelled "Accrued tie-out (shadow)" wherever they are shown beside the
engine's (DEC-77).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import current_values, record_engine_issue
from abacus.modules.tax.entity_schedules import (
    Values,
    capital_rows,
    m2_as_drafted,
    recipients,
)
from abacus.modules.tax.export_entity import allocations
from abacus.modules.tax.workbook_service import WORKBOOK

RETURN_TARGET: Final = "tax_return"
RECON_PREFIX: Final = "recon:"
SHADOW_LABEL: Final = "Accrued tie-out (shadow)"
_PREFIXES: Final = ("schedule_k.", "k1.", "capital.", "m2.")


@dataclass(frozen=True)
class Figure:
    key: str
    label: str
    amount: Decimal


@dataclass(frozen=True)
class ReconRow:
    key: str
    label: str
    accrued: Decimal | None
    engine: Decimal | None

    @property
    def differs(self) -> bool:
        return self.accrued is not None and self.engine is not None and self.accrued != self.engine


def _text(values: Values, key: str) -> str:
    cell = values.get(key)
    value = None if cell is None else cell.get("v")
    return "" if value is None else str(value).strip()


def _amount(cell: Mapping[str, object] | None) -> Decimal | None:
    if cell is None or cell.get("v") in (None, ""):
        return None
    try:
        return Decimal(str(cell.get("v")))
    except InvalidOperation:
        return None


def workbook_figures(
    values: Values, return_id: UUID, known: Mapping[str, UUID]
) -> list[Figure]:
    """Accrued's own figures for every key the engine owns (module docstring), by code."""
    out: list[Figure] = []
    n = 2
    while f"06!A{n}" in values:
        line = _text(values, f"06!A{n}")
        if line and line != "Total":
            out.append(
                Figure(f"schedule_k.{line}", f"Schedule K line {line}",
                       _amount(values.get(f"06!C{n}")) or Decimal(0))
            )  # fmt: skip
        n += 1
    for share in allocations(values, return_id, known):
        out.append(
            Figure(f"k1.{share.partner_ref}.{share.schedule_k_line}",
                   f"K-1 {share.partner} line {share.schedule_k_line}", share.amount)
        )  # fmt: skip
    for row in capital_rows(values, return_id, known):
        out.append(Figure(f"capital.{row.partner_id}.ending", f"Ending capital {row.name}",
                          row.ending))  # fmt: skip
    for number, label, amount in m2_as_drafted(values).lines:
        out.append(Figure(f"m2.{number}", f"M-2 line {number} · {label}", amount))
    return out


def compare(
    figures: Sequence[Figure], engine: Mapping[str, Mapping[str, object]]
) -> list[ReconRow]:
    """One row per figure the engine also carries, and per engine key Accrued has no figure for
    (an extra partner or line is a difference to explain too)."""
    ours = {f.key: f for f in figures}
    rows = [
        ReconRow(f.key, f.label, f.amount, _amount(engine.get(f.key)))
        for f in figures
        if f.key in engine
    ]
    for key in sorted(k for k in engine if k.startswith(_PREFIXES) and k not in ours):
        rows.append(ReconRow(key, key, None, _amount(engine.get(key))))
    return rows


def differences(rows: Sequence[ReconRow]) -> list[ReconRow]:
    """The rows that need explaining: both sides differ, or the engine has a figure Accrued
    lacks."""
    return [r for r in rows if r.differs or (r.accrued is None and r.engine is not None)]


async def reconcile(tenant: TenantContext, return_id: UUID) -> list[ReconRow]:
    """Every compared row, from the workbook now and the engine's approved figures."""
    values = await current_values(tenant, WORKBOOK, return_id)
    known = {name: rid for rid, name in await recipients(tenant, return_id)}
    engine = await current_values(tenant, RETURN_TARGET, return_id)
    engine_owned = {
        k: v for k, v in engine.items() if k.startswith(_PREFIXES)
    }  # the import's entity keys; the return's own fields are not compared here
    return compare(workbook_figures(values, return_id, known), engine_owned)


async def raise_differences(ctx: AuthContext, return_id: UUID) -> int:
    """After an approved import: one `engine_diagnostic` issue per difference (module docstring)."""
    raised = 0
    for row in differences(await reconcile(ctx.tenant, return_id)):
        await record_engine_issue(
            ctx,
            record_type=RETURN_TARGET,
            record_id=return_id,
            work_item_id=return_id,
            source_ref=f"{RECON_PREFIX}{row.key}",
            title=f"CCH reconciliation · {row.label}"[:200],
        )
        raised += 1
    return raised


__all__ = [
    "RECON_PREFIX",
    "SHADOW_LABEL",
    "Figure",
    "ReconRow",
    "compare",
    "differences",
    "raise_differences",
    "reconcile",
    "workbook_figures",
]
