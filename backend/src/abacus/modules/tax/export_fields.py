"""Worksheet fields in the engine exchange (T-04-T30; T-04 §3.10 AC-10.1 to AC-10.4; TXI-01,
TAX-05, TAX-07; ADR-150 W2, ADR P-18; DEC-49, DEC-77, DEC-3405). RED: what leaves the firm for
the engine.

- **Export (AC-10.1).** The W2 workbook carries the values of the **current approved checkpoint**
  only: each field as it stood when that checkpoint was recorded (`review.api.values_as_of`),
  never a later edit. The return's own fields keep their keys; a worksheet field joins under its
  `engine_field_key` (`return_fields`), and only a key the engine's field profile accepts
  (`integrations.api.engine_field_profile`: TR-06, validated keys only); a key outside it blocks
  the export with 409 `engine_field_unmapped` naming the field. Engine-computed lines
  (`derivation = engine`) are the engine's own: they are never sent back. Citations stay in
  Accrued. Code builds every value (ADR-050); no agent can export (the export route is a person's).
- **Import (AC-10.2).** An approved engine import writes each engine-computed line it carries (NY
  tax, NYC tax, the IT-360.1 recompute) onto its worksheet field as an `engine_import` version
  naming the approved import checkpoint, beside the return's own value; nothing changes before a
  person approves the checkpoint (the import stays "Import pending approval").
- **Tie-out (AC-10.3).** On upload, an engine value whose key a worksheet field maps but that
  Accrued computes itself (an input or formula field) is compared in code with Accrued's figure;
  a difference (23,014 vs 23,015) raises one `engine_diagnostic` issue, deduplicated by
  `(work_item_id, source_ref)` with `source_ref = tieout:<engine_field_key>`. The title names the
  line, never a figure (figures are TRI).
- **Out of sync.** A worksheet field edited after the last sync by anything but an import puts the
  return "Out of sync" (`worksheets_changed_since`), as an edit of the return's own fields does.

Never transmit (AC-10.4, R-04): nothing here sends, files or calls the engine.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import UnitOfWork
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations.api import engine_field_profile
from abacus.modules.review.api import (
    changed_since_any,
    checkpoint_recorded_at,
    current_values,
    record_engine_issue,
    record_value,
    values_as_of,
)

RETURN_TARGET: Final = "tax_return"
WORKSHEET_TARGET: Final = "return_worksheet"
TIEOUT_PREFIX: Final = "tieout:"
_ACCRUED_DERIVATIONS: Final = frozenset({"input", "formula", "copy"})


class EngineFieldUnmapped(DomainConflict):
    """A worksheet field's engine key is outside the engine's validated profile (TR-06)."""

    code = "engine_field_unmapped"


@dataclass(frozen=True)
class EngineField:
    worksheet_id: UUID
    field_key: str
    label: str
    engine_field_key: str
    derivation: str


_FIELDS: Final = text(
    "SELECT w.id AS worksheet_id, f.field_key, f.label, f.engine_field_key, f.derivation "
    "FROM return_fields f JOIN return_worksheets w ON w.id = f.worksheet_id "
    "WHERE w.tax_return_id = :r AND w.active AND f.engine_field_key IS NOT NULL "
    "ORDER BY f.engine_field_key, w.sort_order, f.sort_order"
)


async def engine_fields(tenant: TenantContext, return_id: UUID) -> list[EngineField]:
    """The return's active worksheet fields that carry an engine key."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_FIELDS, {"r": return_id})).all()
    return [
        EngineField(
            r.worksheet_id, str(r.field_key), str(r.label), str(r.engine_field_key), r.derivation
        )
        for r in rows
    ]


async def _worksheets(tenant: TenantContext, return_id: UUID) -> list[UUID]:
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    text("SELECT id FROM return_worksheets WHERE tax_return_id = :r AND active"),
                    {"r": return_id},
                )
            ).scalars()
        )


# --- export (AC-10.1) ----------------------------------------------------------------------------


def merge_export(
    return_values: Mapping[str, dict[str, object]],
    fields: Sequence[EngineField],
    worksheet_values: Mapping[UUID, Mapping[str, dict[str, object]]],
    *,
    valid_key: Callable[[str], bool] | None = None,
) -> dict[str, dict[str, object]]:
    """The workbook's values by engine key: the return's own fields, then each Accrued worksheet
    field under its engine key (an engine-computed line is the engine's and is left out)."""
    check = valid_key or engine_field_profile().valid_key
    out = {key: dict(value) for key, value in return_values.items()}
    for field in fields:
        if field.derivation not in _ACCRUED_DERIVATIONS:
            continue
        if not check(field.engine_field_key):
            raise EngineFieldUnmapped(facts={"field_key": field.field_key})
        value = worksheet_values.get(field.worksheet_id, {}).get(field.field_key)
        if value is not None:
            out[field.engine_field_key] = dict(value)
    return out


async def export_values(
    tenant: TenantContext, return_id: UUID, checkpoint_id: UUID
) -> dict[str, dict[str, object]]:
    """Every value the export carries, as of the approved checkpoint (module docstring)."""
    at: datetime = await checkpoint_recorded_at(tenant, checkpoint_id)
    own = (await values_as_of(tenant, RETURN_TARGET, [return_id], at)).get(return_id, {})
    fields = await engine_fields(tenant, return_id)
    sheets = sorted({f.worksheet_id for f in fields})
    return merge_export(own, fields, await values_as_of(tenant, WORKSHEET_TARGET, sheets, at))


# --- import (AC-10.2) and tie-out (AC-10.3) ------------------------------------------------------


async def mirror_engine_lines(
    tx: UnitOfWork,
    tenant: TenantContext,
    *,
    engagement_id: UUID,
    return_id: UUID,
    taken: Sequence[Mapping[str, object]],
    checkpoint_id: UUID,
) -> int:
    """An approved import's engine-computed lines onto their worksheet fields, as `engine_import`
    versions naming the approved checkpoint; answers how many were written."""
    engine_lines = {
        f.engine_field_key: f
        for f in await engine_fields(tenant, return_id)
        if f.derivation == "engine"
    }
    written = 0
    for row in taken:
        field = engine_lines.get(str(row["field_key"]))
        if field is None:
            continue
        await record_value(
            tx,
            engagement_id=engagement_id,
            target_type=WORKSHEET_TARGET,
            target_id=field.worksheet_id,
            field_key=field.field_key,
            value=cast(dict[str, object], row["engine"]),
            value_source="engine_import",
            cause="import",
            checkpoint_id=checkpoint_id,
        )
        written += 1
    return written


def _amount(value: Mapping[str, object] | None) -> Decimal | None:
    if value is None or value.get("v") is None:
        return None
    try:
        return Decimal(str(value.get("v")))
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class TieOut:
    engine_field_key: str
    label: str


def tie_outs(
    engine_values: Mapping[str, Mapping[str, object]],
    fields: Sequence[EngineField],
    accrued: Mapping[UUID, Mapping[str, Mapping[str, object]]],
) -> list[TieOut]:
    """The engine values that differ from Accrued's own figure for the same key (code compares;
    a field with no figure on either side is not a difference)."""
    found: list[TieOut] = []
    for field in fields:
        if field.derivation not in _ACCRUED_DERIVATIONS:
            continue
        engine = _amount(engine_values.get(field.engine_field_key))
        ours = _amount(accrued.get(field.worksheet_id, {}).get(field.field_key))
        if engine is None or ours is None or engine == ours:
            continue
        found.append(TieOut(field.engine_field_key, field.label))
    return found


async def raise_tie_outs(
    ctx: AuthContext, return_id: UUID, engine_values: Mapping[str, Mapping[str, object]]
) -> int:
    """One `engine_diagnostic` issue per differing line, raised once per return and key."""
    fields = await engine_fields(ctx.tenant, return_id)
    current = {
        sheet: await current_values(ctx.tenant, WORKSHEET_TARGET, sheet)
        for sheet in sorted({f.worksheet_id for f in fields})
    }
    raised = 0
    for diff in tie_outs(engine_values, fields, current):
        await record_engine_issue(
            ctx,
            record_type=RETURN_TARGET,
            record_id=return_id,
            work_item_id=return_id,
            source_ref=f"{TIEOUT_PREFIX}{diff.engine_field_key}",
            title=f"Engine tie-out · {diff.label}",
        )
        raised += 1
    return raised


async def worksheets_changed_since(
    tenant: TenantContext, return_id: UUID, since: datetime
) -> bool:
    """Whether a worksheet field changed after the last sync by anything but an import."""
    return await changed_since_any(
        tenant, WORKSHEET_TARGET, await _worksheets(tenant, return_id), since
    )
