"""The deterministic structure proposal (A-09-T13 rest; AUD-32 c; SPEC-658 AC-1.4; DV-2; DEC-5340).

`POST …/consolidations/{cid}/structure/proposal` (the route authorised `consolidation.edit`) reads
the consolidation's OneWorld subsidiary tree (the `group_hierarchy` slot connections registers;
the fake's on synthetic tenants, DV-1), matches each subsidiary to one of the client's entities by
name,
and places them in tiers (`compute.group_structure`). Code, not a model (ADR-050), recorded as the
`audit.group_structure` code run so the dock reads "<person> via Agent", and offered as one P-35
suggestion on `consolidation` / `structure`. Nothing saves (AC-1.4) until Use structure, which
adopts the suggestion (`POST /v1/suggestions/{id}/adopt`), or Edit, which is the PUT.

A field value holds 200 characters, so the tiers are the run's identifier-only output and the
suggestion's value is that output's SHA-256. The applier re-reads the output, checks the digest,
authorises `consolidation.edit` as the adopting person and writes through the PUT's ledger write
in the adopting unit of work; the source connection's coverage extends after commit
(`consolidation.structure_adopted`), as the PUT extends it after its own commit.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.connection_coverage import EntityAlreadyCovered as CoverageTaken
from abacus.kernel.connection_coverage import cover_entities, group_hierarchy
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import DomainEvent, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import (
    AdoptedValue,
    CodeRun,
    CodeStep,
    Fact,
    begin_code_run,
    blocks,
    code_suggestion_output,
    create_code_suggestion,
    fact,
    finish_code_run,
    text_part,
    txt,
)
from abacus.modules.assurance.compute import group_structure as gs
from abacus.modules.assurance.group_contract import StructureInvalid, StructureSourceMissing
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.ledger import api as ledger
from abacus.modules.organisations.api import client_entity_names

AGENT: Final = "audit.group_structure"
TARGET: Final = "consolidation"
FIELD: Final = "structure"
EDIT: Final = "consolidation.edit"
_log = get_logger(__name__)


class ConsolidationStructureAdopted(DomainEvent):
    """A person adopted the proposed structure; the source connection covers its entities."""

    event_type: ClassVar[str] = "consolidation.structure_adopted"

    consolidation_id: Annotated[UUID, classified("internal")]
    connection_id: Annotated[UUID, classified("internal")]
    client_entity_ids: Annotated[list[UUID], classified("internal")]


def _count(fact_id: str, value: int, basis: str) -> Fact:
    return Fact(id=fact_id, kind="count", value=str(value), basis=basis)


async def _candidates(ctx: AuthContext, engagement_id: UUID) -> dict[UUID, str]:
    ref = await get_ref(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        return await client_entity_names(session, ref.client_id)


async def propose(ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID) -> UUID:
    """The suggestion's id. 409 `structure_source_missing` without a OneWorld source or with no
    single top entity matched; 409 `consolidation_not_draft` once finalized or discarded."""
    facts = await ledger.consolidation_facts(ctx.tenant, consolidation_id)
    if facts.work_item_id != work_item_id:
        raise NotFound("consolidation")
    if facts.status != "draft":
        raise ledger.ConsolidationNotDraft
    if facts.source_connection_id is None:
        raise StructureSourceMissing(facts={"reason": "no_source"})
    source = group_hierarchy()
    try:
        placed = gs.propose(source, await _candidates(ctx, facts.engagement_id))
    except gs.StructureTooDeep:
        raise StructureInvalid(facts={"reason": "fourth_tier"}) from None
    except gs.HierarchyInvalid:
        raise StructureSourceMissing(facts={"reason": "source_unreadable"}) from None
    if sum(1 for p in placed if p.level == 1) != 1:
        raise StructureSourceMissing(facts={"reason": "no_single_top"})
    output = gs.output_of(placed)
    tiers = max(p.level for p in placed)
    run = CodeRun(
        agent_id=AGENT,
        engagement_id=facts.engagement_id,
        initiator_user_id=ctx.user_id,
        task_scope=("consolidation.read",),
        steps=(
            CodeStep(
                "consolidation.read_subsidiaries",
                "Read the OneWorld subsidiaries",
                len(source),
                {"matched": len(placed)},
            ),
        ),
        narration=blocks(
            text_part(
                txt("I placed "),
                fact("entities"),
                txt(" of "),
                fact("subsidiaries"),
                txt(" OneWorld subsidiaries in "),
                fact("tiers"),
                txt(" tiers, wholly owned. Nothing is saved until you use or edit it."),
            )
        ),
        facts={
            "entities": _count("entities", len(placed), "subsidiaries matched to entities"),
            "subsidiaries": _count("subsidiaries", len(source), "OneWorld subsidiaries"),
            "tiers": _count("tiers", tiers, "levels in the proposal"),
        },
        output=output,
        work_item_id=work_item_id,
    )
    async with uow(ctx.tenant) as tx:
        run_id = await begin_code_run(
            tx, ctx.tenant_id, AGENT, facts.engagement_id, ctx.user_id, run.task_scope
        )
        suggestion_id = await create_code_suggestion(
            tx,
            ctx.tenant,
            run_id=run_id,
            engagement_id=facts.engagement_id,
            target_type=TARGET,
            target_id=consolidation_id,
            field_key=FIELD,
            proposed_value={"t": "text", "v": gs.digest(output)},
        )
        await finish_code_run(tx, ctx.tenant_id, run_id, run)
    return suggestion_id


async def apply_structure_suggestion(
    tx: UnitOfWork, ctx: AuthContext, adopted: AdoptedValue
) -> None:
    """Use structure: the adopted proposal, checked against its run's output, saved as the PUT
    saves (an edited value is refused: Edit is the PUT)."""
    if adopted.field_key != FIELD or adopted.suggestion_id is None:
        raise StructureInvalid(facts={"reason": "not_a_proposal"})
    found = await code_suggestion_output(tx, adopted.suggestion_id)
    if found is None or adopted.value.get("v") != gs.digest(found[1]):
        raise StructureInvalid(facts={"reason": "proposal_changed"})
    try:
        placed = gs.from_output(found[1])
    except ValueError:
        raise StructureInvalid(facts={"reason": "proposal_changed"}) from None
    facts = await ledger.consolidation_facts(ctx.tenant, adopted.target_id)
    ref = await get_ref(ctx, facts.engagement_id)
    await authorise(ctx, EDIT, ref.resource())
    try:
        await ledger.save_structure(
            tx,
            tenant_id=ctx.tenant_id,
            consolidation_id=adopted.target_id,
            seen=facts.row_version,
            entities=[
                ledger.StructureEntity(
                    client_entity_id=p.client_entity_id,
                    parent_client_entity_id=p.parent_client_entity_id,
                    level=p.level,
                    city=None,
                    component_auditor_id=None,
                )
                for p in placed
            ],
        )
    except ledger.ConsolidationStructureInvalid as exc:
        raise StructureInvalid(facts=exc.facts) from None
    if facts.source_connection_id is not None:
        tx.emit(
            ConsolidationStructureAdopted(
                consolidation_id=adopted.target_id,
                connection_id=facts.source_connection_id,
                client_entity_ids=[p.client_entity_id for p in placed],
            )
        )


async def consolidation_engagement(tenant: TenantContext, consolidation_id: UUID) -> UUID | None:
    try:
        return (await ledger.consolidation_facts(tenant, consolidation_id)).engagement_id
    except NotFound:
        return None


async def on_structure_adopted(event: OutboxEvent) -> None:
    """After commit: the source connection covers the adopted entities (once; a redelivery adds
    none). An entity another live ledger already covers stays as it is (the PUT answers 409)."""
    tenant = TenantContext(event.tenant_id, "system", "consolidation:structure_adopted")
    ids = [UUID(str(i)) for i in cast(list[object], event.payload["client_entity_ids"])]
    try:
        await cover_entities(tenant, UUID(str(event.payload["connection_id"])), ids)
    except CoverageTaken:
        _log.warning("consolidation.structure_adopted.coverage_taken")


SUBSCRIPTIONS: Final = {"consolidation.structure_adopted": on_structure_adopted}
