"""AUD-32's bulk upload and pull-all (A-09-T18 rest; SPEC-658 F2, AC-2.1, AC-2.2; DV-1;
DEC-5329; amber).

- **Bulk upload**: a NetSuite "TB by subsidiary" CSV (connections' pure splitter, through the
  kernel slot `connection_coverage.split_tb_by_subsidiary`; client content untrusted) is matched
  to the consolidation's entities by the client entity's name; each matched subsidiary becomes
  one validated, immutable snapshot attached to the entity's current slot. An unknown subsidiary
  is a row problem: 422 `subsidiary_unknown` naming its position, before anything is stored.
- **Pull-all** (`ConsolidationPullAll`): only on a synthetic tenant until a live OneWorld
  connector exists (DV-1): the fake connector's current trial balance per entity, recorded and
  attached the same way; a refused token leaves the slot `needs_reauth` and is never retried.
- Only a person starts either; nothing here writes to a client's system (CONN-001).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Final
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.clock import system_now
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.errors import DomainInvalid, NotFound
    from abacus.kernel.uow import uow
    from abacus.modules.identity.api import AuthContext, Forbidden
    from abacus.modules.ledger import api as ledger

_SOURCE_CSV: Final = "netsuite_tb_by_subsidiary"
_SOURCE_PULL: Final = "netsuite_oneworld_fake"


class SubsidiaryUnknown(DomainInvalid):
    code = "subsidiary_unknown"


class PullNotAvailable(DomainInvalid):
    code = "pull_all_unavailable"


def _person(ctx: AuthContext) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("consolidation.edit", "role")


async def _entities_by_name(
    tenant: TenantContext, facts: ledger.ConsolidationFacts
) -> dict[str, ledger.EntityRow]:
    from abacus.modules.organisations.api import client_names

    entities = list(facts.entities)
    async with tenant_session(tenant) as session:
        names = await client_names(session, [e.client_entity_id for e in entities])
    return {
        names[e.client_entity_id].client_entity_name.strip().casefold(): e
        for e in entities
        if e.client_entity_id in names
    }


def _current_key(facts: ledger.ConsolidationFacts, entity_id: UUID) -> ledger.SlotKey:
    for key in facts.required:
        if key.consolidation_entity_id == entity_id and key.period_kind == "current":
            return key
    raise NotFound("consolidation_slot")


async def _record_and_attach(
    tenant: TenantContext,
    *,
    consolidation_id: UUID,
    facts: ledger.ConsolidationFacts,
    entity: ledger.EntityRow,
    lines: list[tuple[str, str, Decimal, Decimal]],
    fingerprint: str,
    source: str,
    user_id: UUID,
) -> None:
    from abacus.modules.ledger import api as ledger

    key = _current_key(facts, entity.id)
    tb = ledger.NormalisedTrialBalance(
        period_start=key.period_start,
        period_end=key.period_end,
        currency="USD",
        lines=tuple(
            ledger.LedgerLine(code, name, debit, credit, f"{source}:{code}")
            for code, name, debit, credit in lines
        ),
        declared_debit=sum((d for _, _, d, _ in lines), Decimal(0)),
        declared_credit=sum((c for _, _, _, c in lines), Decimal(0)),
    )
    async with uow(tenant) as tx:
        snapshot = await ledger.record_snapshot(
            tx,
            client_entity_id=entity.client_entity_id,
            period_start=tb.period_start,
            period_end=tb.period_end,
            tb=tb,
            raw_fingerprint=fingerprint,
            pulled_at=system_now(),
            source=source,
        )
        await ledger.attach_trial_balance(
            tx,
            tenant_id=tenant.tenant_id,
            consolidation_id=consolidation_id,
            key=key,
            snapshot_id=snapshot.id,
            source="upload",
            evidence_version_id=None,
            user_id=user_id,
        )


async def bulk_upload(
    ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID, data: bytes
) -> None:
    """Split, match every subsidiary, then record and attach each (nothing stored on a refusal)."""
    _person(ctx)
    from abacus.kernel.connection_coverage import split_tb_by_subsidiary
    from abacus.modules.assurance.group_tb import (
        _facts,  # pyright: ignore[reportPrivateUsage] -- the module's own scope check
    )

    facts = await _facts(ctx, work_item_id, consolidation_id)
    parts = split_tb_by_subsidiary(data)
    by_name = await _entities_by_name(ctx.tenant, facts)
    for position, subsidiary in enumerate(parts, start=1):
        if subsidiary.strip().casefold() not in by_name:
            raise SubsidiaryUnknown(facts={"position": position})
    fingerprint = hashlib.sha256(data).hexdigest()
    for subsidiary, lines in parts.items():
        await _record_and_attach(
            ctx.tenant,
            consolidation_id=consolidation_id,
            facts=facts,
            entity=by_name[subsidiary.strip().casefold()],
            lines=list(lines),
            fingerprint=fingerprint,
            source=_SOURCE_CSV,
            user_id=ctx.user_id,
        )


# --- ConsolidationPullAll ------------------------------------------------------------------------


@dataclass(frozen=True)
class PullAllInput:
    tenant_id: str
    consolidation_id: str
    user_id: str


@activity.defn(name="assurance.consolidation.pull_all")
async def pull_all_activity(p: PullAllInput) -> int:
    """The fake OneWorld connector's current TB per entity, recorded and attached; a refused
    token marks the slot `needs_reauth` (never retried). Returns how many were attached."""
    from abacus.kernel.connection_coverage import pull_group_tbs

    tenant = TenantContext(UUID(p.tenant_id), "system", f"consolidation_pull:{p.consolidation_id}")
    consolidation_id = UUID(p.consolidation_id)
    facts = await ledger.consolidation_facts(tenant, consolidation_id)
    by_name = await _entities_by_name(tenant, facts)
    attached = 0
    for subsidiary, lines in pull_group_tbs():
        entity = by_name.get(subsidiary.strip().casefold())
        if entity is None:
            continue
        if lines is None:  # a refused token: the slot reads Needs reauth, never retried
            async with uow(tenant) as tx:
                await ledger.mark_slot_needs_reauth(
                    tx,
                    tenant_id=tenant.tenant_id,
                    key=_current_key(facts, entity.id),
                    user_id=UUID(p.user_id),
                )
            continue
        body = "|".join(f"{code}:{debit}:{credit}" for code, _, debit, credit in lines)
        await _record_and_attach(
            tenant,
            consolidation_id=consolidation_id,
            facts=facts,
            entity=entity,
            lines=list(lines),
            fingerprint=hashlib.sha256(f"{subsidiary}|{body}".encode()).hexdigest(),
            source=_SOURCE_PULL,
            user_id=UUID(p.user_id),
        )
        attached += 1
    return attached


@workflow.defn(name="ConsolidationPullAll")
class ConsolidationPullAll:
    @workflow.run
    async def run(self, p: PullAllInput) -> int:
        return await workflow.execute_activity(
            "assurance.consolidation.pull_all",
            p,
            result_type=int,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=1),  # a refused token is never retried
        )


async def start_pull_all(ctx: AuthContext, work_item_id: UUID, consolidation_id: UUID) -> str:
    """Start one pull per consolidation at a time (the workflow id is the consolidation's)."""
    _person(ctx)
    from abacus.kernel.dispatch import dispatch
    from abacus.modules.assurance.group_tb import (
        _facts,  # pyright: ignore[reportPrivateUsage] -- the module's own scope check
    )
    from abacus.modules.identity.api import is_synthetic_firm

    await _facts(ctx, work_item_id, consolidation_id)
    if not await is_synthetic_firm(ctx.tenant):
        raise PullNotAvailable(facts={"connector": "netsuite_oneworld"})
    workflow_id = f"consolidation_pull:{ctx.tenant_id}:{consolidation_id}"
    await dispatch(
        ConsolidationPullAll,
        PullAllInput(str(ctx.tenant_id), str(consolidation_id), str(ctx.user_id)),
        id=workflow_id,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return workflow_id


WORKFLOWS: Final[dict[type, str]] = {ConsolidationPullAll: "background"}
ACTIVITIES: Final[tuple[object, ...]] = (pull_all_activity,)
