"""Consolidation routes' service (A-09-T13; SPEC-658 F1, AC-1.1 to AC-1.3; DEC-5070): assurance
hosts the C9 v2.1 routes and calls the ledger's consolidation service (ledger stays free of other
modules, DEC-66).

The route gated the engagement (walls 404, independence 403), the `group_audit` capability and
the action. Here: the consolidation must be the work item's; names come from organisations and
identity; a covering connection must cover the entity (connections); finalize is a person's act
(a manager or the EP by the matrix), refuses a missing TB (`trial_balance_missing`) and adopts one
TB of record per entity, whose adoption starts that entity's mapping run (A-03's subscriber:
five entities, five runs). Every figure is code's (ADR-050).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._statuses import (
    ConsolidationLockStatus,
    ConsolidationStatus,
    ConsolidationTbStatus,
)
from abacus.kernel.connection_coverage import EntityAlreadyCovered as CoverageTaken
from abacus.kernel.connection_coverage import cover_entities, covers
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.assurance.group_contract import (
    ConsolidationEntityOut,
    ConsolidationFinalizeIn,
    ConsolidationIn,
    ConsolidationOut,
    EntityAlreadyCovered,
    StructureIn,
    StructureInvalid,
    TbAttachIn,
    TbNotNeededIn,
    TrialBalanceMissing,
    TrialBalanceSlotOut,
)
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of
from abacus.modules.ledger import api as ledger
from abacus.modules.ledger.api import TrialBalanceExists
from abacus.modules.organisations.api import entity_display_name

_SLOTS: Final = uuid.UUID("6f0c1d1e-9a09-4c13-8e2a-c0750118a7e1")  # missing-slot ids (uuid5)
_ETAG: Final = re.compile(r'^(?:W/)?"?(\d{1,9})"?$')
Action = Literal["consolidation.edit", "consolidation.finalize", "consolidation.lock"]
_ACTIONS: Final[tuple[Action, ...]] = (
    "consolidation.edit",
    "consolidation.finalize",
    "consolidation.lock",
)
_PERIOD_WORDS: Final = {"current": "", "prior": "Prior"}
_LABEL_WORDS: Final = {"interim": "Interim", "standard": "Year end", "prior": "Prior"}


class IfMatchInvalid(DomainInvalid):
    code = "if_match_invalid"


def seen_version(if_match: str) -> int:
    found = _ETAG.fullmatch(if_match.strip())
    if found is None:
        raise IfMatchInvalid
    return int(found.group(1))


def slot_id(key: ledger.SlotKey) -> UUID:
    """A missing slot's stable id (nothing is stored until a TB is attached or not needed)."""
    return uuid.uuid5(
        _SLOTS, f"{key.consolidation_entity_id}:{key.label}:{key.period_kind}:{key.period_end}"
    )


async def _facts(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID
) -> ledger.ConsolidationFacts:
    facts = await ledger.consolidation_facts(ctx.tenant, consolidation_id)
    if facts.work_item_id != work_item_id:
        raise NotFound("consolidation")
    return facts


async def _may(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


async def _auditor_names(ctx: AuthContext, ids: Sequence[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            text("SELECT id, organisation_name FROM component_auditors WHERE id = ANY(:i)"),
            {"i": list(ids)},
        )
        return {cast(UUID, r[0]): str(r[1]) for r in rows}


def _slot_out(key: ledger.SlotKey, stored: ledger.SlotRow | None) -> TrialBalanceSlotOut:
    return TrialBalanceSlotOut(
        id=stored.id if stored is not None else slot_id(key),
        label=key.label,
        period_kind=key.period_kind,
        period_start=key.period_start,
        period_end=key.period_end,
        state=ConsolidationTbStatus(stored.state if stored is not None else "missing"),
        file_name=None,
        total_debits=stored.total_debits if stored is not None else None,
        not_needed_reason=stored.not_needed_reason if stored is not None else None,
    )


async def consolidation_view(
    ctx: AuthContext, facts: ledger.ConsolidationFacts
) -> ConsolidationOut:
    names = {
        e.id: (await entity_display_name(ctx.tenant, e.client_entity_id)) or "—"
        for e in facts.entities
    }
    auditors = await _auditor_names(
        ctx, [e.component_auditor_id for e in facts.entities if e.component_auditor_id]
    )
    entities: list[ConsolidationEntityOut] = []
    for e in facts.entities:
        keys = [k for k in facts.required if k.consolidation_entity_id == e.id]
        entities.append(
            ConsolidationEntityOut(
                id=e.id,
                client_entity_id=e.client_entity_id,
                name=names[e.id],
                level=e.level,
                parent_id=e.parent_id,
                ownership_pct=Decimal(100),
                city=e.city,
                component_auditor_name=auditors.get(e.component_auditor_id)
                if e.component_auditor_id
                else None,
                trial_balances=[_slot_out(k, facts.slot_of(k)) for k in keys],
            )
        )
    attached = [s for s in facts.slots if s.state == "attached"]
    interim = sum(
        (s.total_debits or Decimal(0) for s in attached if s.key.period_kind == "current"),
        Decimal("0.00"),
    )
    missing = [
        f"{names.get(k.consolidation_entity_id, '—')} · {_LABEL_WORDS.get(k.label, k.label)}"
        for k in facts.missing()
    ]
    finalized_by = None
    if facts.finalized_by is not None:
        finalized_by = (await names_of([facts.finalized_by])).get(facts.finalized_by)
    ref = await get_ref(ctx, facts.engagement_id)
    allowed: list[Action] = []
    for action in _ACTIONS:
        open_for = {
            "consolidation.edit": facts.status == "draft",
            "consolidation.finalize": facts.status == "draft" and not missing,
            "consolidation.lock": facts.status == "finalized",
        }[action]
        if open_for and await _may(ctx, action, ref.resource()):
            allowed.append(action)
    return ConsolidationOut(
        id=facts.id,
        name=facts.name,
        status=ConsolidationStatus(facts.status),
        lock_state=ConsolidationLockStatus(facts.lock_state),
        year_end=facts.year_end,
        reporting_currency="USD",
        interim_period_end=facts.interim_period_end,
        prior_period_end=facts.prior_period_end,
        entities=entities,
        tiers=max((e.level for e in facts.entities), default=0),
        interim_total_debits=interim,
        all_balanced=all(s.total_debits == s.total_credits for s in attached),
        missing=missing,
        finalized_by_name=finalized_by,
        finalized_at=facts.finalized_at,
        row_version=facts.row_version,
        allowed_actions=allowed,
    )


async def get(ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID) -> ConsolidationOut:
    return await consolidation_view(ctx, await _facts(ctx, work_item_id, consolidation_id))


async def create(
    ctx: AuthContext, work_item_id: UUID, engagement_id: UUID, body: ConsolidationIn, key: str
) -> ConsolidationOut:
    ref = await get_ref(ctx, engagement_id)
    if body.source_connection_id is not None and not await covers(
        ctx.tenant, body.source_connection_id, ref.client_entity_id
    ):
        raise NotFound("connection")

    async def run() -> tuple[int, dict[str, object]]:
        async with uow(ctx.tenant) as tx:
            made = await ledger.create_consolidation(
                tx,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                user_id=ctx.user_id,
                name=body.name,
                year_end=body.year_end,
                interim_period_end=body.interim_period_end,
                prior_period_end=body.prior_period_end,
                source_connection_id=body.source_connection_id,
            )
        return 201, {"id": str(made)}

    stored = await idempotent(
        ctx.tenant,
        route="consolidation.create",
        key=key,
        body={"work_item_id": str(work_item_id), **body.model_dump(mode="json")},
        run=run,
    )
    return await get(ctx, work_item_id, UUID(str(stored.body["id"])))


async def edit(
    ctx: AuthContext,
    work_item_id: UUID,
    consolidation_id: UUID,
    body: ConsolidationIn,
    if_match: str,
) -> ConsolidationOut:
    await _facts(ctx, work_item_id, consolidation_id)
    async with uow(ctx.tenant) as tx:
        await ledger.edit_consolidation(
            tx,
            consolidation_id,
            seen_version(if_match),
            name=body.name,
            year_end=body.year_end,
            interim_period_end=body.interim_period_end,
            prior_period_end=body.prior_period_end,
            source_connection_id=body.source_connection_id,
        )
    return await get(ctx, work_item_id, consolidation_id)


async def discard(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID
) -> ConsolidationOut:
    await _facts(ctx, work_item_id, consolidation_id)
    async with uow(ctx.tenant) as tx:
        await ledger.discard_consolidation(tx, consolidation_id)
    return await get(ctx, work_item_id, consolidation_id)


async def save_structure(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID, body: StructureIn, if_match: str
) -> ConsolidationOut:
    facts = await _facts(ctx, work_item_id, consolidation_id)
    entities = [
        ledger.StructureEntity(
            client_entity_id=e.client_entity_id,
            parent_client_entity_id=e.parent_client_entity_id,
            level=e.level,
            city=e.city,
            component_auditor_id=e.component_auditor_id,
        )
        for e in body.entities
    ]
    try:
        async with uow(ctx.tenant) as tx:
            await ledger.save_structure(
                tx,
                tenant_id=ctx.tenant_id,
                consolidation_id=consolidation_id,
                seen=seen_version(if_match),
                entities=entities,
            )
    except ledger.ConsolidationStructureInvalid as exc:
        raise StructureInvalid(facts=exc.facts) from None
    if facts.source_connection_id is not None:
        try:
            await cover_entities(
                ctx.tenant, facts.source_connection_id, [e.client_entity_id for e in entities]
            )
        except CoverageTaken:
            raise EntityAlreadyCovered from None
    return await get(ctx, work_item_id, consolidation_id)


def _key_for(
    facts: ledger.ConsolidationFacts, entity_id: UUID, label: str, period_kind: str
) -> ledger.SlotKey:
    for k in facts.required:
        if (k.consolidation_entity_id, k.label, k.period_kind) == (entity_id, label, period_kind):
            return k
    raise NotFound("trial_balance_slot")


async def attach(
    ctx: AuthContext,
    work_item_id: UUID,
    consolidation_id: UUID,
    entity_id: UUID,
    body: TbAttachIn,
) -> TrialBalanceSlotOut:
    facts = await _facts(ctx, work_item_id, consolidation_id)
    entity = next((e for e in facts.entities if e.id == entity_id), None)
    if entity is None:
        raise NotFound("consolidation_entity")
    key = _key_for(facts, entity_id, body.label, body.period_kind)
    if body.source == "connection":
        if body.connection_id is None or not await covers(
            ctx.tenant, body.connection_id, entity.client_entity_id
        ):
            raise NotFound("connection")
        snapshot = await ledger.snapshot_for_slot(
            ctx.tenant, entity.client_entity_id, key.period_end
        )
    elif body.source == "evidence":
        if body.evidence_version_id is None:
            raise NotFound("evidence_version")
        snapshot = await ledger.snapshot_for_slot(
            ctx.tenant,
            entity.client_entity_id,
            key.period_end,
            evidence_version_id=body.evidence_version_id,
        )
    else:
        if body.upload_id is None:
            raise NotFound("ledger_snapshot")
        snapshot = await ledger.snapshot_for_slot(
            ctx.tenant, entity.client_entity_id, key.period_end, snapshot_id=body.upload_id
        )
    async with uow(ctx.tenant) as tx:
        await ledger.attach_trial_balance(
            tx,
            tenant_id=ctx.tenant_id,
            consolidation_id=consolidation_id,
            key=key,
            snapshot_id=snapshot,
            source=body.source,
            evidence_version_id=body.evidence_version_id,
            user_id=ctx.user_id,
        )
    after = await ledger.consolidation_facts(ctx.tenant, consolidation_id)
    return _slot_out(key, after.slot_of(key))


async def not_needed(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID, tb_id: UUID, body: TbNotNeededIn
) -> TrialBalanceSlotOut:
    facts = await _facts(ctx, work_item_id, consolidation_id)
    key = next(
        (
            k
            for k in facts.required
            if slot_id(k) == tb_id or ((s := facts.slot_of(k)) is not None and s.id == tb_id)
        ),
        None,
    )
    if key is None:
        raise NotFound("trial_balance_slot")
    async with uow(ctx.tenant) as tx:
        await ledger.mark_not_needed(
            tx,
            tenant_id=ctx.tenant_id,
            consolidation_id=consolidation_id,
            key=key,
            reason=body.reason,
            user_id=ctx.user_id,
        )
    after = await ledger.consolidation_facts(ctx.tenant, consolidation_id)
    return _slot_out(key, after.slot_of(key))


async def finalize(
    ctx: AuthContext,
    work_item_id: UUID,
    consolidation_id: UUID,
    body: ConsolidationFinalizeIn,
    key: str,
) -> ConsolidationOut:
    """A person's act; one TB of record per entity, whose adoption starts its mapping run."""
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("consolidation.finalize", "role")
    facts = await _facts(ctx, work_item_id, consolidation_id)

    async def run() -> tuple[int, dict[str, object]]:
        try:
            async with uow(ctx.tenant) as tx:
                done = await ledger.finalize_consolidation(
                    tx, facts, tenant_id=ctx.tenant_id, seen=body.seen_version, user_id=ctx.user_id
                )
                for entity_id, snapshot_id, label, _start, _end in done.entity_snapshots:
                    try:  # refused before it writes anything, so the transaction goes on
                        await ledger.adopt_trial_balance(
                            tx,
                            tenant_id=ctx.tenant_id,
                            engagement_id=facts.engagement_id,
                            work_item_id=work_item_id,
                            client_entity_id=entity_id,
                            snapshot_id=snapshot_id,
                            prior_snapshot_id=None,
                            label=label,
                            display_unit="cents",
                            user_id=ctx.user_id,
                            actor_kind="human",
                        )
                    except TrialBalanceExists:
                        continue  # the entity's TB of record exists: its mapping already runs
        except ledger.ConsolidationTbMissing:
            raise TrialBalanceMissing(facts={"missing": len(facts.missing())}) from None
        return 200, {"id": str(consolidation_id)}

    await idempotent(
        ctx.tenant,
        route="consolidation.finalize",
        key=key,
        body={"consolidation_id": str(consolidation_id), "seen_version": body.seen_version},
        run=run,
    )
    return await get(ctx, work_item_id, consolidation_id)
