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
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

TARGET: Final = "proposed_entry"
APPROVE: Final = "elimination.approve"
EDIT: Final = "elimination.edit"
ZERO: Final = Decimal("0.00")


class UnbalancedEntry(DomainConflict):
    code = "unbalanced_entry"


class ConsolidationLocked(DomainConflict):
    code = "consolidation_locked"


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
    "status FROM proposed_entries WHERE id = :id AND kind = 'elimination'"
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
    lines = tuple(EliminationLine(str(r[0]), r[1], Decimal(r[2]), Decimal(r[3])) for r in rows)
    return EliminationView(
        id=head["id"],
        display_code=str(head["display_code"]),
        level=int(rows[0][4]) if rows else 1,
        description=str(head["description"] or ""),
        status=str(head["status"]),
        lines=lines,
        total_debit=sum((ln.debit for ln in lines), ZERO),
        total_credit=sum((ln.credit for ln in lines), ZERO),
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
