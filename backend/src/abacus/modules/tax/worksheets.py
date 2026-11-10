"""The worksheets service (T-04-T16; SPEC-649; TAX-05; ADR-161; DEC-3209).

- **The tree** (`GET /v1/returns/{id}/worksheets`): every active worksheet in order, with its
  group and sub-head (`group_path` "Income > Sch E"), the default TSJ, whether it is new this year
  and whether a person has edited it.
- **The fields** (`GET /v1/worksheets/{id}/fields?q=`): sections with fields, each with its value,
  view state (imported, edited, proposed, recomputed, signed off), the provenance line, its
  citation count and, for an engine field, the import label (read-only).
- **A person's edit** goes through `PUT /v1/fields/return_worksheet/<id>/<key>/value` (P-04's
  route: the citation note is the required reason, `seen_seq` the expected version, 409 when
  stale). T-04-T15's applier writes the value; this module then recomputes the derived lines in
  code (`worksheet_formulas`), each recorded as a `formula` version with cause `recompute`, in the
  same unit of work, so the one human checkpoint covers them and the section's sign-off reads
  stale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.review.api import edited_by_a_person, latest_sources, record_value
from abacus.modules.tax.worksheet_formulas import recompute

READ: Final = "return_worksheet.read"


@dataclass(frozen=True)
class Node:
    worksheet_id: UUID
    title: str
    group: str
    sub_head: str | None
    tsj: str | None
    new_this_year: bool
    edited: bool


@dataclass(frozen=True)
class FieldRow:
    field_key: str
    label: str
    value: Decimal | None
    state: str
    provenance: str | None
    citations: int
    engine_label: str | None
    seen_seq: int


@dataclass(frozen=True)
class FieldGroup:
    key: str
    title: str
    fields: list[FieldRow]


async def _authorised(ctx: AuthContext, work_item_id: UUID) -> UUID:
    engagement = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")
    ref = await get_ref(ctx, engagement)
    await authorise(ctx, READ, ref.resource())
    return engagement


def _split(group_path: str | None) -> tuple[str, str | None]:
    if not group_path:
        return "Other", None
    parts = [p.strip() for p in group_path.replace("\u203a", ">").split(">") if p.strip()]
    return parts[0], (parts[1] if len(parts) > 1 else None)


async def tree(ctx: AuthContext, return_id: UUID) -> list[Node]:
    await _authorised(ctx, return_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT w.id, w.title, w.group_path, w.default_tsj, w.new_vs_prior_year "
                    "FROM return_worksheets w WHERE w.tax_return_id = :r AND w.active "
                    "ORDER BY w.sort_order, w.key"
                ),
                {"r": return_id},
            )
        ).all()
    edited = await edited_by_a_person(ctx.tenant, WORKSHEET, [r.id for r in rows])
    found: list[Node] = []
    for r in rows:
        group, sub = _split(r.group_path)
        tsj = r.default_tsj if r.default_tsj in ("T", "S", "J") else None
        found.append(
            Node(r.id, r.title, group, sub, tsj, bool(r.new_vs_prior_year), r.id in edited)
        )
    return found


def _money(value: object) -> Decimal | None:
    if not isinstance(value, dict):
        return None
    raw = cast(dict[str, object], value).get("v")
    try:
        return None if raw is None else Decimal(str(raw)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


WORKSHEET: Final = "return_worksheet"
_STATE: Final = {
    "engine_import": "imported",
    "human": "edited",
    "agent_suggested": "proposed",
    "formula": "recomputed",
}


async def fields(ctx: AuthContext, worksheet_id: UUID, q: str | None) -> list[FieldGroup]:
    async with tenant_session(ctx.tenant) as session:
        work_item = await session.scalar(
            text("SELECT tax_return_id FROM return_worksheets WHERE id = :w"), {"w": worksheet_id}
        )
    if work_item is None:
        raise NotFound("return_worksheet")
    await _authorised(ctx, cast(UUID, work_item))
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT s.key AS section_key, s.name AS section_name, f.field_key, f.label, "
                    "f.line_ref, f.derivation, f.engine_field_key, f.current_value, "
                    "coalesce(f.current_fvv_seq, 0) AS seq "
                    "FROM return_fields f JOIN return_worksheet_sections s ON s.id = f.section_id "
                    "WHERE f.worksheet_id = :w ORDER BY s.sort_order, s.key, f.sort_order, "
                    "f.field_key"
                ),
                {"w": worksheet_id},
            )
        ).all()
    latest = await latest_sources(ctx.tenant, WORKSHEET, [worksheet_id])
    needle = (q or "").strip().casefold()
    sections: dict[str, FieldGroup] = {}
    for r in rows:
        if (
            needle
            and needle not in r.label.casefold()
            and needle not in (r.line_ref or "").casefold()
        ):
            continue
        known, cites = latest.get((worksheet_id, r.field_key), (None, 0))
        source = known or ("engine_import" if r.derivation == "engine" else None)
        state = _STATE.get(source or "", "imported")
        section = sections.setdefault(r.section_key, FieldGroup(r.section_key, r.section_name, []))
        section.fields.append(
            FieldRow(
                r.field_key,
                r.label,
                _money(r.current_value),
                state,
                None,
                cites,
                r.engine_field_key if r.derivation == "engine" else None,
                int(r.seq),
            )
        )
    return list(sections.values())


async def recompute_after_edit(
    tx: UnitOfWork, engagement_id: UUID, worksheet_id: UUID
) -> dict[str, Decimal]:
    """After a person's edit (in its unit of work): every formula field that moved, recorded as a
    `formula` version with cause `recompute`."""
    rows = (
        await tx.session.execute(
            text(
                "SELECT field_key, derivation, formula_ref, current_value FROM return_fields "
                "WHERE worksheet_id = :w"
            ),
            {"w": worksheet_id},
        )
    ).all()
    values = {r.field_key: _money(r.current_value) for r in rows}
    formulas = {r.field_key: str(r.formula_ref) for r in rows if r.derivation == "formula"}
    if not formulas:
        return {}
    moved = recompute(values, formulas)
    for key, value in moved.items():
        typed = {"t": "decimal", "v": str(value)}
        await tx.session.execute(
            text(
                "UPDATE return_fields SET current_value = CAST(:v AS jsonb), "
                "updated_at = clock_timestamp() WHERE worksheet_id = :w AND field_key = :k"
            ),
            {"v": json.dumps(typed), "w": worksheet_id, "k": key},
        )
        await record_value(
            tx,
            engagement_id=engagement_id,
            target_type="return_worksheet",
            target_id=worksheet_id,
            field_key=key,
            value=typed,
            value_source="formula",
            cause="recompute",
        )
    return moved
