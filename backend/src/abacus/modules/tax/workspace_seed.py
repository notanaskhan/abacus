"""The synthetic return workspace recorder (T-04-T28; T-04 §5.3; DEC-1530, DEC-3406). RED path is
not touched: this writes only a synthetic firm's worksheets.

Brightwater Hale's Feld return needs its worksheets, sections and field values in the database so
`make seed-demo` and fixture mode show the same TAX-05, TAX-06 and TXI-01 figures. No product path
creates worksheets yet (the drafter proposes into existing ones, T-04-T25), so the scenario writes
them here, through the unit of work, as the person the design names, with an audit event per
worksheet; each value is a field version (`review.api.record_value`, value source
`agent_suggested`, cause `import`: the roll-forward the agent drafted) and the field's cached
current value (`worksheet_review.write_field`), so the reads and the hashes are the product's.

Synthetic firms only: a real firm is 404 (DEC-1530). Values are TRI and never logged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID, uuid5

from sqlalchemy import text

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import work_item_engagement
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    engagement_resource,
    is_synthetic_firm,
)
from abacus.modules.review.api import content_hash, record_value
from abacus.modules.tax.worksheet_review import write_field

_NS: Final = UUID("7a3f1c22-28d4-5e8b-9b0e-0c4d7f2a2028")
EMPTY_HASH: Final = content_hash({"fields": []})
Derivation = Literal["input", "formula", "engine", "copy"]


@dataclass(frozen=True)
class SeedField:
    key: str
    label: str
    value: Decimal | None
    line_ref: str | None = None
    tsj: str = "J"
    derivation: Derivation = "input"
    engine_field_key: str | None = None
    formula_ref: str | None = None
    new_this_year_note: str | None = None


@dataclass(frozen=True)
class SeedSection:
    key: str
    name: str
    fields: tuple[SeedField, ...]


@dataclass(frozen=True)
class SeedWorksheet:
    key: str
    form_code: str
    title: str
    group_path: str | None
    jurisdiction: str
    default_tsj: str
    sections: tuple[SeedSection, ...] = field(default_factory=tuple[SeedSection, ...])
    new_vs_prior_year: bool = False


def worksheet_id_for(return_id: UUID, key: str) -> UUID:
    return uuid5(_NS, f"{return_id}:{key}")


async def record_synthetic_workspace(
    ctx: AuthContext, return_id: UUID, worksheets: Sequence[SeedWorksheet]
) -> list[UUID]:
    """The return's worksheets as the scenario names them; answers their ids. A worksheet that
    exists already is left as it is (the load is idempotent)."""
    if not await is_synthetic_firm(ctx.tenant):
        raise NotFound("tax_return")
    engagement_id = await work_item_engagement(ctx.tenant, return_id)
    if engagement_id is None:
        raise NotFound("tax_return")
    await authorise(
        ctx, "return_worksheet.read", await engagement_resource(ctx.tenant, engagement_id)
    )
    ids: list[UUID] = []
    for order, sheet in enumerate(worksheets):
        sheet_id = worksheet_id_for(return_id, sheet.key)
        ids.append(sheet_id)
        async with uow(ctx.tenant) as tx:
            inserted = (
                await tx.session.execute(
                    text(
                        "INSERT INTO return_worksheets (id, tenant_id, engagement_id, "
                        "tax_return_id, key, form_code, title, group_path, jurisdiction, "
                        "default_tsj, origin, new_vs_prior_year, sort_order, content_hash) "
                        "VALUES (:id, :t, :e, :r, :key, :form, :title, :group, :j, :tsj, "
                        "'agent', :new, :order, :h) ON CONFLICT (tax_return_id, key) DO NOTHING "
                        "RETURNING id"
                    ),
                    {
                        "id": sheet_id,
                        "t": ctx.tenant_id,
                        "e": engagement_id,
                        "r": return_id,
                        "key": sheet.key,
                        "form": sheet.form_code,
                        "title": sheet.title,
                        "group": sheet.group_path,
                        "j": sheet.jurisdiction,
                        "tsj": sheet.default_tsj,
                        "new": sheet.new_vs_prior_year,
                        "order": order,
                        "h": EMPTY_HASH,
                    },
                )
            ).first()
            if inserted is None:
                continue
            for s_order, section in enumerate(sheet.sections):
                section_id = uuid5(_NS, f"{sheet_id}:{section.key}")
                await tx.session.execute(
                    text(
                        "INSERT INTO return_worksheet_sections (id, tenant_id, engagement_id, "
                        "tax_return_id, worksheet_id, key, name, sort_order, content_hash) VALUES "
                        "(:id, :t, :e, :r, :w, :key, :name, :order, :h)"
                    ),
                    {
                        "id": section_id,
                        "t": ctx.tenant_id,
                        "e": engagement_id,
                        "r": return_id,
                        "w": sheet_id,
                        "key": section.key,
                        "name": section.name,
                        "order": s_order,
                        "h": EMPTY_HASH,
                    },
                )
                for f_order, seed in enumerate(section.fields):
                    await tx.session.execute(
                        text(
                            "INSERT INTO return_fields (tenant_id, engagement_id, tax_return_id, "
                            "worksheet_id, section_id, field_key, line_ref, label, tsj, "
                            "value_type, derivation, formula_ref, engine_field_key, "
                            "new_this_year_note, sort_order) VALUES (:t, :e, :r, :w, :s, :key, "
                            ":line, :label, :tsj, 'amount', :d, :formula, :engine, :note, :order)"
                        ),
                        {
                            "t": ctx.tenant_id,
                            "e": engagement_id,
                            "r": return_id,
                            "w": sheet_id,
                            "s": section_id,
                            "key": seed.key,
                            "line": seed.line_ref,
                            "label": seed.label,
                            "tsj": seed.tsj,
                            "d": seed.derivation,
                            "formula": seed.formula_ref,
                            "engine": seed.engine_field_key,
                            "note": seed.new_this_year_note,
                            "order": f_order,
                        },
                    )
            for section in sheet.sections:
                for seed in section.fields:
                    if seed.value is None or seed.derivation == "engine":
                        continue
                    value: dict[str, object] = {"t": "decimal", "v": str(seed.value)}
                    await record_value(
                        tx,
                        engagement_id=engagement_id,
                        target_type="return_worksheet",
                        target_id=sheet_id,
                        field_key=seed.key,
                        value=value,
                        value_source="agent_suggested",
                        cause="import",
                    )
                    await write_field(tx, sheet_id, seed.key, value)
            tx.record(
                "return_worksheet.seeded",
                target=Target("return_worksheet", sheet_id),
                after=Ref(fields=sum(len(s.fields) for s in sheet.sections)),
                scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
            )
    return ids


def total(fields: Sequence[SeedField]) -> Decimal:
    """Code foots a worksheet's parts (ADR-050)."""
    return sum((f.value for f in fields if f.value is not None), Decimal(0))
