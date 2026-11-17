"""AUD-33's consolidated trial balance, lock and reopen, and the workbook (A-09-T19 rest;
SPEC-658 F4, AC-4.1 to AC-4.5; DEC-5328; amber).

- **Inputs are code's.** Each entity's TB of record on the engagement, mapped by C9 v2 (its FS
  lines' net, debits positive), and the consolidation's posted eliminations; the engine
  (`ledger.api.consolidate`) computes every column, total, tie and attribution. Nothing here adds.
- **Levels.** Level 1 is every entity. Level 2 is the first level-2 entity with entities under it
  (by position) and those entities, with the level-2 eliminations.
- **Lock and reopen** are a person's (a Manager or the EP; the matrix), reopen with a reason.
- An entity whose TB is not yet mapped is left out of the read (`mapped` counts it), never
  guessed.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.adjustments.api import eliminations as adj_eliminations
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.ledger import api as ledger

Section = Literal["assets", "liabilities_equity", "income"]
_SECTION: Final[dict[str, Section]] = {
    "assets": "assets",
    "liabilities": "liabilities_equity",
    "equity": "liabilities_equity",
    "revenue": "income",
    "expenses": "income",
}


async def _facts(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID
) -> ledger.ConsolidationFacts:
    facts = await ledger.consolidation_facts(ctx.tenant, consolidation_id)
    if facts.work_item_id != work_item_id:
        raise NotFound("consolidation")
    return facts


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _tbs(
    tenant: TenantContext, facts: ledger.ConsolidationFacts
) -> tuple[dict[str, list[ledger.ConsolidationTbLine]], int, int]:
    """Each mapped entity's lines by its key (the consolidation entity's id), and the counts of
    entities mapped and entities in the structure."""
    by_entity = {
        tb.client_entity_id: tb.id
        for tb in await ledger.engagement_trial_balances(tenant, facts.engagement_id)
        if tb.client_entity_id is not None
    }
    found: dict[str, list[ledger.ConsolidationTbLine]] = {}
    for entity in facts.entities:
        tb_id = by_entity.get(entity.client_entity_id)
        if tb_id is None:
            continue
        mapped = await ledger.mapped_trial_balance(tenant, facts.engagement_id, tb_id)
        if mapped is None or mapped.unmapped:
            continue
        found[str(entity.id)] = [
            ledger.ConsolidationTbLine(
                caption=line.fs_line_label,
                section=_SECTION.get(line.grouping_class, "assets"),
                amount=line.debit - line.credit,
            )
            for line in mapped.lines
            if line.debit or line.credit
        ]
    return found, len(found), len(facts.entities)


async def mapped_lines(
    tenant: TenantContext, facts: ledger.ConsolidationFacts
) -> dict[str, list[ledger.ConsolidationTbLine]]:
    """A-09-T34: each mapped entity's FS lines by its structure key (the proposer's input)."""
    found, _, _ = await _tbs(tenant, facts)
    return found


def _members(facts: ledger.ConsolidationFacts, level: int) -> list[str]:
    ordered = sorted(facts.entities, key=lambda e: e.position)
    if level == 1:
        return [str(e.id) for e in ordered]
    parents = [e for e in ordered if e.level == 2 and any(c.parent_id == e.id for c in ordered)]
    if not parents:
        return []
    head = parents[0]
    return [str(head.id), *(str(e.id) for e in ordered if e.parent_id == head.id)]


async def _posted(tenant: TenantContext, consolidation_id: UUID) -> list[ledger.Elimination]:
    views = await adj_eliminations.eliminations_of(tenant, consolidation_id)
    return [
        ledger.Elimination(
            code=v.display_code,
            level=v.level,
            lines=tuple(
                ledger.ConsolidationEliminationLine(ln.caption, ln.debit, ln.credit)
                for ln in v.lines
            ),
        )
        for v in views
        if v.status == "posted"
    ]


async def levels(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID
) -> tuple[list[ledger.ConsolidationLevel], int, int]:
    """Every level the structure has, computed by the engine (the route authorised the read)."""
    return await levels_for(ctx.tenant, await _facts(ctx, work_item_id, consolidation_id))


async def levels_for(
    tenant: TenantContext, facts: ledger.ConsolidationFacts
) -> tuple[list[ledger.ConsolidationLevel], int, int]:
    """`levels` for an owner already scoped to the consolidation (AUD-34's card provider)."""
    tbs, mapped, accounts = await _tbs(tenant, facts)
    posted = await _posted(tenant, facts.id)
    out: list[ledger.ConsolidationLevel] = []
    for level in (1, 2):
        members = [m for m in _members(facts, level) if m in tbs]
        if not members:
            continue
        out.append(
            ledger.consolidate(
                {m: tbs[m] for m in members}, members, level=level, eliminations=posted
            )
        )
    return out, mapped, accounts


async def lock(ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID) -> None:
    _person(ctx, "consolidation.lock")
    facts = await _facts(ctx, work_item_id, consolidation_id)
    async with uow(ctx.tenant) as tx:
        await ledger.lock_consolidation(tx, facts, tenant_id=ctx.tenant_id, user_id=ctx.user_id)


async def reopen(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID, reason: str
) -> None:
    _person(ctx, "consolidation.lock")
    facts = await _facts(ctx, work_item_id, consolidation_id)
    async with uow(ctx.tenant) as tx:
        await ledger.reopen_consolidation(
            tx, facts, tenant_id=ctx.tenant_id, user_id=ctx.user_id, reason=reason
        )


async def workbook(ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID) -> bytes:
    """Every level as its own sheet, the entities named by their client entity (code's figures)."""
    from abacus.kernel.db import tenant_session
    from abacus.modules.organisations.api import client_names

    facts = await _facts(ctx, work_item_id, consolidation_id)
    found, _, _ = await levels(ctx, work_item_id, consolidation_id)
    async with tenant_session(ctx.tenant) as session:
        names = await client_names(session, [e.client_entity_id for e in facts.entities])
    by_key = {
        str(e.id): names[e.client_entity_id].client_entity_name
        if e.client_entity_id in names
        else str(e.id)
        for e in facts.entities
    }
    by_key[ledger.ELIMINATIONS_COLUMN] = "Eliminations"
    by_key[ledger.CONSOLIDATED_COLUMN] = "Consolidated"
    return ledger.render_consolidation_levels(found, by_key)


def cell_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def level_of(found: Sequence[ledger.ConsolidationLevel], level: int) -> ledger.ConsolidationLevel:
    chosen = next((lv for lv in found if lv.level == level), None)
    if chosen is None:
        raise NotFound("consolidation_level")
    return chosen
