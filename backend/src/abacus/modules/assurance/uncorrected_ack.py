"""C18's `uncorrected_misstatements` kind (R-02-T15; R-02 §3, AC-12; SPEC-646; DEC-3113).

The client's acknowledgement of the uncorrected misstatements, on A-06's frozen SUM snapshot (the
`rep_letter_attachment` one A-07's representation letter attaches). Code computes every figure
(ADR-050): the net effect is the snapshot's own frozen total (`iron_curtain`, the net-assets
effect), stored with the snapshot's engine version and inputs hash, never re-added by the
browser or the client. The row is insert-only and human-only (0710): a client person with a
live grant and a fresh second factor, once per snapshot and contact. `uncorrected_misstatements.
acknowledged` tells A-07's rep letter and the EP and manager.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.assurance.events import UncorrectedMisstatementsAcknowledged
from abacus.modules.engagements.api import (
    ApprovalFacts,
    ApprovalItem,
    ApprovalLine,
    ClientDecision,
    ClientDecisionContext,
    ItemChanged,
)

KIND: Final = "uncorrected_misstatements"
# Constant SQL only; values are bound parameters.
_ON_SCOPE: Final = text(
    "SELECT s.id, s.engagement_id, s.work_item_id, s.version_no, s.engine_version, "
    "s.inputs_hash, s.totals, (SELECT a.acknowledged_at FROM "
    "uncorrected_misstatement_acknowledgements a WHERE a.sum_snapshot_id = s.id "
    "ORDER BY a.acknowledged_at DESC LIMIT 1) AS acknowledged_at FROM sum_snapshots s "
    "WHERE s.purpose = 'rep_letter_attachment' "
    "AND (s.work_item_id = :scope OR s.engagement_id = :scope) "
    "AND s.version_no = (SELECT max(version_no) FROM sum_snapshots x "
    "WHERE x.work_item_id = s.work_item_id AND x.purpose = 'rep_letter_attachment')"
)
_ONE: Final = text(
    "SELECT s.id, s.engagement_id, s.work_item_id, s.version_no, s.engine_version, "
    "s.inputs_hash, s.totals, (SELECT a.acknowledged_at FROM "
    "uncorrected_misstatement_acknowledgements a WHERE a.sum_snapshot_id = s.id "
    "ORDER BY a.acknowledged_at DESC LIMIT 1) AS acknowledged_at FROM sum_snapshots s "
    "WHERE s.purpose = 'rep_letter_attachment' AND s.id = :id"
)
_PASSED: Final = text(
    "SELECT id FROM audit_misstatements WHERE work_item_id = :wi AND status = 'passed_on_sum' "
    "ORDER BY created_at, id"
)


def net_effect(totals: object) -> Decimal:
    """The snapshot's frozen net-assets effect: read, never recomputed."""
    raw = cast(dict[str, object], totals).get("iron_curtain")
    if raw is None:
        raise ItemChanged
    return Decimal(str(raw)).quantize(Decimal("0.01"))


def parts(totals: object) -> tuple[ApprovalLine, ...]:
    """R-02-T19: the net effect's two figures as the snapshot froze them (would increase, would
    decrease), for the acknowledgement's sentence; none from a snapshot frozen before they were."""
    t = cast(dict[str, object], totals)
    up, down = t.get("iron_curtain_increase"), t.get("iron_curtain_decrease")
    if up is None or down is None:
        return ()
    q = Decimal("0.01")
    return (
        ApprovalLine("Would increase net assets", debit=Decimal(str(up)).quantize(q)),
        ApprovalLine("Would decrease net assets", credit=Decimal(str(down)).quantize(q)),
    )


def seen_hash(snapshot_id: UUID, inputs_hash: str, net: Decimal) -> str:
    return hashlib.sha256(f"{snapshot_id}:{inputs_hash}:{net}".encode()).hexdigest()


def _item(r: object) -> ApprovalItem:
    row = cast(dict[str, object], r)
    net = net_effect(row["totals"])
    snapshot_id = cast(UUID, row["id"])
    return ApprovalItem(
        kind=KIND,
        item_id=snapshot_id,
        scope_kind="work_item",
        scope_id=cast(UUID, row["work_item_id"]),
        sent_to_client=True,
        title="Uncorrected misstatements",
        state="acknowledged" if row["acknowledged_at"] is not None else "waiting",
        seen_hash=seen_hash(snapshot_id, str(row["inputs_hash"]), net),
        amount=net,
        lines=parts(row["totals"]),
        decided_at=cast(object, row["acknowledged_at"]),  # type: ignore[arg-type]  # a timestamptz
    )


class UncorrectedMisstatements:
    """The provider (registered from `assurance.api`)."""

    async def items(self, tenant: TenantContext, scope_id: UUID) -> Sequence[ApprovalItem]:
        async with tenant_session(tenant) as session:
            rows = (await session.execute(_ON_SCOPE, {"scope": scope_id})).mappings().all()
        return [_item(dict(r)) for r in rows]

    async def item(self, tenant: TenantContext, item_id: UUID) -> ApprovalItem | None:
        async with tenant_session(tenant) as session:
            row = (await session.execute(_ONE, {"id": item_id})).mappings().first()
        return None if row is None else _item(dict(row))

    async def decide(
        self,
        tx: UnitOfWork,
        item_id: UUID,
        decision: ClientDecision,
        context: ClientDecisionContext,
    ) -> ApprovalItem:
        if decision.decision != "acknowledge":
            raise ItemChanged
        row = (await tx.session.execute(_ONE, {"id": item_id})).mappings().first()
        if row is None:
            raise NotFound("sum_snapshot")
        current = _item(dict(row))
        if current.seen_hash != decision.seen_hash:
            raise ItemChanged  # the snapshot moved since the client read it
        work_item_id = cast(UUID, row["work_item_id"])
        engagement_id = cast(UUID, row["engagement_id"])
        entries = [r.id for r in await tx.session.execute(_PASSED, {"wi": work_item_id})]
        if not entries:
            raise ItemChanged
        await tx.session.execute(
            text(
                "INSERT INTO uncorrected_misstatement_acknowledgements (tenant_id, engagement_id, "
                "work_item_id, sum_snapshot_id, approval_item_id, net_effect, engine_version, "
                "inputs_hash, entry_ids, contact_id, actor_user_id, actor_kind, actor_id, "
                "principal_kind, grant_id, mfa_verified_at, seen_hash) VALUES "
                "((SELECT tenant_id FROM sum_snapshots WHERE id = :s), :e, :wi, :s, :s, :net, "
                ":ev, :ih, :entries, :contact, :user, 'human', :actor, 'client', :grant, :mfa, "
                ":seen)"
            ),
            {
                "s": item_id,
                "e": engagement_id,
                "wi": work_item_id,
                "net": current.amount,
                "ev": row["engine_version"],
                "ih": row["inputs_hash"],
                "entries": entries,
                "contact": context.contact_id,
                "user": context.user_id,
                "actor": str(context.user_id),
                "grant": context.grant_id,
                "mfa": context.mfa_verified_at,
                "seen": decision.seen_hash,
            },
        )
        tx.emit(
            UncorrectedMisstatementsAcknowledged(
                sum_snapshot_id=item_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                contact_id=context.contact_id,
            )
        )
        tx.record(
            "uncorrected_misstatements.acknowledged",
            target=Target("sum_snapshot", item_id),
            after=Ref(
                contact=context.contact_id,
                grant=context.grant_id,
                entries=len(entries),
                inputs_hash=str(row["inputs_hash"]),
            ),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        return ApprovalItem(
            kind=KIND,
            item_id=item_id,
            scope_kind="work_item",
            scope_id=work_item_id,
            sent_to_client=True,
            title="Uncorrected misstatements",
            state="acknowledged",
            seen_hash=current.seen_hash,
            amount=current.amount,
        )

    async def facts(self, tenant: TenantContext, item_id: UUID) -> ApprovalFacts:
        found = await self.item(tenant, item_id)
        if found is None:
            raise NotFound("sum_snapshot")
        return ApprovalFacts(True, found.scope_id)  # an audit client (attest)


PROVIDER: Final = UncorrectedMisstatements()


def register() -> None:
    from abacus.modules.engagements.api import register_client_approval_kind

    register_client_approval_kind(KIND, PROVIDER)


__all__ = ["KIND", "PROVIDER", "net_effect", "register", "seen_hash"]
