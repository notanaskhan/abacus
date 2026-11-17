"""Consolidation eliminations on C8 (A-09-T20; A-09 §3 F4; SPEC-658; AUD-33; DEC-5313; red).

An elimination is a proposed entry of kind `elimination` on the group audit's work item, tied to
one consolidation, posting only to Accrued's consolidation layer (0896; ADR-040: never a client
system, never a posting batch, never a snapshot).

- **Create and edit** while `proposed`: lines by caption and the entity each eliminates, at one
  consolidation level; the server computes debits, credits and off-by.
- **Approve** (`elimination.approve`, a Manager or the EP, a live person; the matrix, this
  service and the CHECKs refuse an agent or the system): 409 `unbalanced_entry` unless debits
  equal credits; one or a batch of items.
- **Post**: an approved elimination moves to `posted` on the consolidation layer: the status
  column alone; no posting batch, no ledger snapshot is touched.
- **Reject** with a reason code. **A locked consolidation** refuses every change (409
  `consolidation_locked`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden, authorise

TARGET: Final = "proposed_entry"
APPROVE: Final = "elimination.approve"
EDIT: Final = "elimination.edit"
ZERO: Final = Decimal("0.00")


class UnbalancedEntry(DomainConflict):
    code = "unbalanced_entry"


class ConsolidationLocked(DomainConflict):
    code = "consolidation_locked"


class EliminationStale(DomainConflict):
    code = "version_stale"


class NotProposed(DomainConflict):
    code = "transition_not_available"


@dataclass(frozen=True)
class EliminationLine:
    caption: str
    client_entity_id: UUID
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class EliminationView:
    id: UUID
    display_code: str
    level: int
    description: str
    status: str
    lines: tuple[EliminationLine, ...]
    total_debit: Decimal
    total_credit: Decimal
    # A-09-T34 (DEC-5522): an agent-proposed entry names its run, code's computation and its
    # verified citations (identifiers only); a person's entry carries none.
    proposed_by_run_id: UUID | None = None
    computation: str | None = None
    citation_ids: tuple[UUID, ...] = ()

    @property
    def off_by(self) -> Decimal:
        return (self.total_debit - self.total_credit).quantize(Decimal("0.01"))


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def _code(caption: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", caption).strip("_")[:60]
    return slug or "caption"


_HEAD: Final = text(
    "SELECT id, engagement_id, work_item_id, consolidation_id, display_code, description, "
    "status, source_ref FROM proposed_entries WHERE id = :id AND kind = 'elimination'"
)
_LINES: Final = text(
    "SELECT account_name, client_entity_id, debit, credit, consolidation_level FROM "
    "proposed_entry_lines WHERE entry_id = :id ORDER BY line_no"
)
_NEXT_CODE: Final = text(
    "SELECT count(*) + 1 FROM proposed_entries WHERE consolidation_id = :c "
    "AND kind = 'elimination'"
)


async def _resource(ctx: AuthContext, engagement_id: UUID) -> object:
    from abacus.modules.engagements.api import engagement_resource_of

    return await engagement_resource_of(ctx.tenant, engagement_id)


async def _locked(tenant: TenantContext, consolidation_id: UUID) -> bool:
    """The consolidation's lock, read through ledger's API (ledger owns the consolidation)."""
    from abacus.modules.ledger.api import consolidation_facts

    facts = await consolidation_facts(tenant, consolidation_id)
    return facts.lock_state == "locked"


async def view(tenant: TenantContext, entry_id: UUID) -> EliminationView:
    async with tenant_session(tenant) as session:
        head = (await session.execute(_HEAD, {"id": entry_id})).mappings().first()
        if head is None:
            raise NotFound(TARGET)
        rows = (await session.execute(_LINES, {"id": entry_id})).all()
    # An edit zeroes the replaced lines (lines are never deleted; A-09-T20 rest, DEC-5328).
    live = [r for r in rows if Decimal(r[2]) or Decimal(r[3])] or list(rows)
    lines = tuple(EliminationLine(str(r[0]), r[1], Decimal(r[2]), Decimal(r[3])) for r in live)
    run_id, computation, cited = _proposal_of(head["source_ref"])
    return EliminationView(
        id=head["id"],
        display_code=str(head["display_code"]),
        level=int(live[-1][4]) if live else 1,
        description=str(head["description"] or ""),
        status=str(head["status"]),
        lines=lines,
        total_debit=sum((ln.debit for ln in lines), ZERO),
        total_credit=sum((ln.credit for ln in lines), ZERO),
        proposed_by_run_id=run_id,
        computation=computation,
        citation_ids=cited,
    )


def _proposal_of(source_ref: object) -> tuple[UUID | None, str | None, tuple[UUID, ...]]:
    """The run, computation and citations an agent proposal recorded in `source_ref`."""
    if not isinstance(source_ref, dict) or "run_id" not in source_ref:
        return None, None, ()
    ref = cast(dict[str, object], source_ref)
    cited = cast(list[object], ref.get("citation_ids") or [])
    return (
        UUID(str(ref["run_id"])),
        str(ref.get("computation") or "") or None,
        tuple(UUID(str(c)) for c in cited),
    )


async def propose_elimination(
    ctx: AuthContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    consolidation_id: UUID,
    level: int,
    description: str,
    lines: Sequence[EliminationLine],
) -> EliminationView:
    """A person's elimination, proposed (an off-balance entry is kept and shows its off-by)."""
    _human(ctx, EDIT)
    await authorise(ctx, EDIT, await _resource(ctx, engagement_id))  # type: ignore[arg-type] -- a Resource
    if await _locked(ctx.tenant, consolidation_id):
        raise ConsolidationLocked(facts={"consolidation": str(consolidation_id)})
    amount = max(sum((ln.debit for ln in lines), ZERO), sum((ln.credit for ln in lines), ZERO))
    async with uow(ctx.tenant) as tx:
        n = int(await tx.session.scalar(_NEXT_CODE, {"c": consolidation_id}) or 1)
        number = int(
            await tx.session.scalar(
                text(
                    "SELECT coalesce(max(number), 0) + 1 FROM proposed_entries "
                    "WHERE work_item_id = :w AND kind = 'elimination'"
                ),
                {"w": work_item_id},
            )
            or 1
        )
        entry_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, kind, "
                    "number, ref, description, amount, account_class, threshold_result, "
                    "is_attest_client, status, created_by_kind, created_by_id, consolidation_id, "
                    "posting_target, display_code) VALUES (:t, :e, :w, 'elimination', :n, :ref, "
                    ":d, :a, 'consolidation', 'review_required', true, 'review_required', "
                    "'human', :cid, :c, 'consolidation_layer', :code) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "n": number,
                    "ref": f"ELIM-{number}",
                    "d": description.strip()[:300],
                    "a": amount,
                    "cid": ctx.tenant.actor_id,
                    "c": consolidation_id,
                    "code": f"E{n}",
                },
            ),
        )
        for line_no, ln in enumerate(lines, start=1):
            await tx.session.execute(
                text(
                    "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, "
                    "entry_id, line_no, account_code, account_name, debit, credit, "
                    "client_entity_id, consolidation_level) VALUES (:t, :e, :w, :id, :n, :code, "
                    ":name, :dr, :cr, :ent, :lvl)"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "id": entry_id,
                    "n": line_no,
                    "code": _code(ln.caption),
                    "name": ln.caption[:200],
                    "dr": ln.debit,
                    "cr": ln.credit,
                    "ent": ln.client_entity_id,
                    "lvl": level,
                },
            )
        tx.record(
            "elimination.proposed",
            target=Target(TARGET, entry_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await view(ctx.tenant, entry_id)


AGENT_PROPOSE: Final = "elimination.agent_propose"


async def propose_by_agent(
    agent: AgentContext,
    *,
    work_item_id: UUID,
    consolidation_id: UUID,
    level: int,
    description: str,
    lines: Sequence[EliminationLine],
    computation: str,
    citation_ids: Sequence[UUID],
) -> EliminationView:
    """A-09-T34 (DEC-5522): `consolidation.elimination_proposer`'s entry, proposed only. The
    agent's task scope must name `elimination.agent_propose`; it never approves or posts (those
    actions deny the agent). The entry is the agent's, on behalf of the run's initiator, and
    names its run; code computed every amount before this call."""
    if agent.engagement_id is None:
        raise NotFound("engagement")
    engagement_id = agent.engagement_id
    await authorise(agent, AGENT_PROPOSE, await _resource_of(agent.tenant, engagement_id))  # type: ignore[arg-type] -- a Resource
    if await _locked(agent.tenant, consolidation_id):
        raise ConsolidationLocked(facts={"consolidation": str(consolidation_id)})
    debit = sum((ln.debit for ln in lines), ZERO)
    credit = sum((ln.credit for ln in lines), ZERO)
    if debit != credit or debit == ZERO:
        raise UnbalancedEntry(facts={"lines": len(lines)})
    source_ref = {
        "run_id": str(agent.agent_run_id),
        "computation": computation[:500],
        "citation_ids": [str(c) for c in citation_ids],
    }
    async with uow(agent.tenant) as tx:
        n = int(await tx.session.scalar(_NEXT_CODE, {"c": consolidation_id}) or 1)
        number = int(
            await tx.session.scalar(
                text(
                    "SELECT coalesce(max(number), 0) + 1 FROM proposed_entries "
                    "WHERE work_item_id = :w AND kind = 'elimination'"
                ),
                {"w": work_item_id},
            )
            or 1
        )
        entry_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, kind, "
                    "number, ref, description, amount, account_class, threshold_result, "
                    "is_attest_client, status, created_by_kind, created_by_id, "
                    "on_behalf_of_user_id, source_ref, consolidation_id, posting_target, "
                    "display_code) VALUES (:t, :e, :w, 'elimination', :n, :ref, :d, :a, "
                    "'consolidation', 'review_required', true, 'review_required', 'agent', "
                    ":run, :by, CAST(:src AS jsonb), :c, 'consolidation_layer', :code) "
                    "RETURNING id"
                ),
                {
                    "t": agent.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "n": number,
                    "ref": f"ELIM-{number}",
                    "d": description.strip()[:300],
                    "a": debit,
                    "run": str(agent.agent_run_id),
                    "by": agent.initiator.user_id,
                    "src": json.dumps(source_ref),
                    "c": consolidation_id,
                    "code": f"E{n}",
                },
            ),
        )
        for line_no, ln in enumerate(lines, start=1):
            await tx.session.execute(
                text(
                    "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, "
                    "entry_id, line_no, account_code, account_name, debit, credit, "
                    "client_entity_id, consolidation_level) VALUES (:t, :e, :w, :id, :n, :code, "
                    ":name, :dr, :cr, :ent, :lvl)"
                ),
                {
                    "t": agent.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "id": entry_id,
                    "n": line_no,
                    "code": _code(ln.caption),
                    "name": ln.caption[:200],
                    "dr": ln.debit,
                    "cr": ln.credit,
                    "ent": ln.client_entity_id,
                    "lvl": level,
                },
            )
        tx.record(
            "elimination.proposed",
            target=Target(TARGET, entry_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
            after=Ref(run=agent.agent_run_id),
        )
    return await view(agent.tenant, entry_id)


async def _resource_of(tenant: TenantContext, engagement_id: UUID) -> object:
    from abacus.modules.engagements.api import engagement_resource_of

    return await engagement_resource_of(tenant, engagement_id)


async def approve(ctx: AuthContext, entry_ids: Sequence[UUID]) -> list[EliminationView]:
    """A Manager or the EP approves one or a batch; each must balance (409 otherwise)."""
    _human(ctx, APPROVE)
    out: list[EliminationView] = []
    for entry_id in entry_ids:
        async with tenant_session(ctx.tenant) as session:
            head = (await session.execute(_HEAD, {"id": entry_id})).mappings().first()
        if head is None:
            raise NotFound(TARGET)
        await authorise(ctx, APPROVE, await _resource(ctx, head["engagement_id"]))  # type: ignore[arg-type] -- a Resource
        if await _locked(ctx.tenant, head["consolidation_id"]):
            raise ConsolidationLocked(facts={"consolidation": str(head["consolidation_id"])})
        current = await view(ctx.tenant, entry_id)
        if current.status not in ("proposed", "review_required", "within_threshold"):
            raise NotProposed(facts={"status": current.status})
        if current.off_by != 0:
            raise UnbalancedEntry(facts={"entry": str(entry_id)})
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                text(
                    "UPDATE proposed_entries SET status = 'approved', version = version + 1 "
                    "WHERE id = :id AND status IN ('proposed', 'review_required', "
                    "'within_threshold')"
                ),
                {"id": entry_id},
            )
            tx.record("elimination.approved", target=Target(TARGET, entry_id))
        out.append(await view(ctx.tenant, entry_id))
    return out


async def post(ctx: AuthContext, entry_id: UUID) -> EliminationView:
    """Approved → posted on the consolidation layer; no posting batch, no snapshot."""
    _human(ctx, APPROVE)
    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(_HEAD, {"id": entry_id})).mappings().first()
    if head is None:
        raise NotFound(TARGET)
    await authorise(ctx, APPROVE, await _resource(ctx, head["engagement_id"]))  # type: ignore[arg-type] -- a Resource
    if await _locked(ctx.tenant, head["consolidation_id"]):
        raise ConsolidationLocked(facts={"consolidation": str(head["consolidation_id"])})
    if head["status"] != "approved":
        raise NotProposed(facts={"status": str(head["status"])})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE proposed_entries SET status = 'posted', version = version + 1 "
                "WHERE id = :id AND status = 'approved'"
            ),
            {"id": entry_id},
        )
        tx.record(
            "elimination.posted",
            target=Target(TARGET, entry_id),
            after=Ref(consolidation=head["consolidation_id"]),
        )
    return await view(ctx.tenant, entry_id)


# --- the AUD-33 routes' rest (A-09-T20; DEC-5328) ----------------------------------------------

_OF: Final = text(
    "SELECT id FROM proposed_entries WHERE consolidation_id = :c AND kind = 'elimination' "
    "ORDER BY created_at, id"
)
_EDITABLE: Final = frozenset({"proposed", "review_required", "within_threshold"})


async def eliminations_of(tenant: TenantContext, consolidation_id: UUID) -> list[EliminationView]:
    """A consolidation's eliminations in the order proposed (the caller authorised the read)."""
    async with tenant_session(tenant) as session:
        ids = [cast(UUID, r[0]) for r in await session.execute(_OF, {"c": consolidation_id})]
    return [await view(tenant, i) for i in ids]


async def edit_elimination(
    ctx: AuthContext,
    entry_id: UUID,
    *,
    level: int,
    description: str,
    lines: Sequence[EliminationLine],
    seen_version: int,
) -> EliminationView:
    """A person's edit while Proposed: the old lines are zeroed and the new ones appended (lines
    are never deleted); 409 `version_stale` on a stale If-Match, `consolidation_locked` once
    locked."""
    _human(ctx, EDIT)
    async with tenant_session(ctx.tenant) as session:
        head = (
            (
                await session.execute(
                    text(
                        "SELECT engagement_id, work_item_id, consolidation_id, status, version "
                        "FROM proposed_entries WHERE id = :id AND kind = 'elimination'"
                    ),
                    {"id": entry_id},
                )
            )
            .mappings()
            .first()
        )
    if head is None:
        raise NotFound(TARGET)
    await authorise(ctx, EDIT, await _resource(ctx, head["engagement_id"]))  # type: ignore[arg-type] -- a Resource
    if await _locked(ctx.tenant, head["consolidation_id"]):
        raise ConsolidationLocked(facts={"consolidation": str(head["consolidation_id"])})
    if head["status"] not in _EDITABLE:
        raise NotProposed(facts={"status": str(head["status"])})
    if int(head["version"]) != seen_version:
        raise EliminationStale(facts={"entry": str(entry_id)})
    amount = max(sum((ln.debit for ln in lines), ZERO), sum((ln.credit for ln in lines), ZERO))
    async with uow(ctx.tenant) as tx:
        bumped = await tx.session.scalar(
            text(
                "UPDATE proposed_entries SET description = :d, amount = :a, version = version + 1 "
                "WHERE id = :id AND version = :v RETURNING version"
            ),
            {"d": description[:300], "a": amount, "id": entry_id, "v": seen_version},
        )
        if bumped is None:
            raise EliminationStale(facts={"entry": str(entry_id)})
        await tx.session.execute(
            text("UPDATE proposed_entry_lines SET debit = 0, credit = 0 WHERE entry_id = :id"),
            {"id": entry_id},
        )
        last = int(
            await tx.session.scalar(
                text(
                    "SELECT coalesce(max(line_no), 0) FROM proposed_entry_lines "
                    "WHERE entry_id = :id"
                ),
                {"id": entry_id},
            )
            or 0
        )
        for line_no, ln in enumerate(lines, start=last + 1):
            await tx.session.execute(
                text(
                    "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, "
                    "entry_id, line_no, account_code, account_name, debit, credit, "
                    "client_entity_id, consolidation_level) VALUES (:t, :e, :w, :id, :n, :code, "
                    ":name, :dr, :cr, :ent, :lvl)"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": head["engagement_id"],
                    "w": head["work_item_id"],
                    "id": entry_id,
                    "n": line_no,
                    "code": _code(ln.caption),
                    "name": ln.caption[:200],
                    "dr": ln.debit,
                    "cr": ln.credit,
                    "ent": ln.client_entity_id,
                    "lvl": level,
                },
            )
        tx.record("elimination.edited", target=Target(TARGET, entry_id), after=Ref(version=bumped))
    return await view(ctx.tenant, entry_id)


async def reject_elimination(ctx: AuthContext, entry_id: UUID, reason: str) -> EliminationView:
    """A person rejects with a reason (sealed on the decision row, A-06's reject)."""
    _human(ctx, APPROVE)
    found = await view(ctx.tenant, entry_id)
    async with tenant_session(ctx.tenant) as session:
        engagement = await session.scalar(
            text("SELECT engagement_id FROM proposed_entries WHERE id = :id"), {"id": entry_id}
        )
    await authorise(ctx, APPROVE, await _resource(ctx, cast(UUID, engagement)))  # type: ignore[arg-type] -- a Resource
    if found.status == "posted":
        raise NotProposed(facts={"status": found.status})
    from abacus.modules.adjustments.decisions import reject_with_note

    await reject_with_note(ctx, entry_id, "elimination_rejected", reason)
    return await view(ctx.tenant, entry_id)
