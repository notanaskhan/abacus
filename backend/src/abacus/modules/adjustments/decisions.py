"""A-06-T10: the adjustments service, part 2 (C8; A-06 §4.3; SPEC-642; DEC-2062). PROTECTED (red).

Every decision on a proposed entry is a named person's, written insert-only to
`proposed_entry_decisions` (0643: `actor_kind = 'human'` and the session's own actor):

- **Approve and send** (`send`, manager or EP; fresh MFA in the matrix): human-only in five layers
  (the matrix, `require_live_human` here, 0643's CHECKs on the decision and the batch, the grant
  only a person's decision can carry, and the audit event). One unit of work writes the named
  person's approval batch, one decision row per entry and an approval grant whose effect (the
  C18 send to the client) is held 10 seconds: nothing reaches the client before the relay consumes
  the grant. **Undo** inside the window voids it and writes `send_undone`.
- **Batch** (`create_batch`): within-threshold entries approved together by a named person.
- **Reject** (`reject`): the firm's own reject, with a reason code.
- **Record mode** (`record_client_decision`): the client's decision from an email, with the email
  as evidence: accepted -> Client approved, declined -> Client declined, a question stays.
- Client decisions call the owners' hooks (`register_entry_decision_hook`): A-06's misstatements
  read Booked on an approval and Uncorrected on a decline (assurance registers it; fail closed:
  no hook, nothing else changes).

The C18 port is a slot (`register_client_delivery`): until R-02's consumer suite passes, nothing is
registered and the held send delivers nothing (fail closed). No route or adapter posts an entry
to any client system (ADR-040; `pe_posting_dormant`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.adjustments.entries import TARGET, engagement_of
from abacus.modules.engagements.api import lock_ref
from abacus.modules.identity.api import AuthContext, Forbidden, issue_grant, void_grant

SEND: Final = "proposed_entry.send_to_client"
UNDO_WINDOW: Final = timedelta(seconds=10)  # DEC-24
GRANT_LIFETIME: Final = timedelta(days=7)
BATCH_TARGET: Final = "approval_batch"
_SENDABLE: Final = frozenset({"within_threshold", "review_required", "approved"})
_BATCHABLE: Final = frozenset({"within_threshold"})
_REJECTABLE: Final = frozenset({"proposed", "within_threshold", "review_required", "approved"})
_RECORDABLE: Final = frozenset({"approved"})
ClientDecision = Literal["client_accepted", "client_declined", "client_question"]
_AUDIT: Final = {
    "rejected": "proposed_entry.rejected",
    "client_accepted": "proposed_entry.client_decision_recorded",
    "client_declined": "proposed_entry.client_decision_recorded",
    "client_question": "proposed_entry.client_decision_recorded",
}


class EntriesMoved(DomainConflict):
    """An entry changed since the person read it (its version) or is in another state."""

    code = "version_conflict"


class UndoWindowClosed(DomainConflict):
    code = "undo_window_closed"


class EntryNotSendable(DomainInvalid):
    code = "entry_not_sendable"


class EntriesSentToClient(DomainEvent):
    """The C18 send, held on the approval grant (consumed after the 10-second Undo window)."""

    event_type: ClassVar[str] = "proposed_entries.sent_to_client"

    approval_batch_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    entry_ids: Annotated[list[UUID], classified("internal")]
    recipient_contact_id: Annotated[UUID, classified("internal")]
    wording_template_version_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class Sent:
    approval_batch_id: UUID
    undo_until: datetime


# --- slots ---------------------------------------------------------------------------------------

ClientDelivery = Callable[[TenantContext, OutboxEvent], Awaitable[None]]
_DELIVERY: list[ClientDelivery] = []
# (unit of work, entry id, the misstatement it came from or None, the client's decision)
DecisionHook = Callable[[UnitOfWork, UUID, UUID | None, ClientDecision], Awaitable[None]]
_HOOKS: list[DecisionHook] = []


def register_client_delivery(delivery: ClientDelivery) -> None:
    """C18's port (R-02): the one adapter that shows the batch to the client."""
    if _DELIVERY and _DELIVERY[0] is not delivery:
        raise ValueError("a client delivery is already registered")
    _DELIVERY[:] = [delivery]


def register_entry_decision_hook(hook: DecisionHook) -> None:
    if hook not in _HOOKS:
        _HOOKS.append(hook)


async def on_sent(event: OutboxEvent) -> None:
    """The held send's consumer: the relay consumed the grant, so the window passed without an
    Undo. With no C18 port registered, nothing is delivered (fail closed)."""
    if not _DELIVERY:
        return
    tenant = TenantContext(event.tenant_id, "system", "adjustments.send")
    await _DELIVERY[0](tenant, event)


SUBSCRIPTIONS: Final = {EntriesSentToClient.event_type: on_sent}


# --- helpers -------------------------------------------------------------------------------------


def _live_human(ctx: AuthContext, action: str) -> None:
    """`require_live_human` (INV-1)."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def send_digest(batch_id: UUID, entry_ids: Sequence[UUID], recipient: UUID, wording: UUID) -> str:
    body = json.dumps(
        {
            "batch": str(batch_id),
            "entries": sorted(str(e) for e in entry_ids),
            "recipient": str(recipient),
            "wording": str(wording),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def _locked_entries(
    tx: UnitOfWork, work_item_id: UUID, entry_ids: Sequence[UUID]
) -> list[dict[str, object]]:
    rows = (
        await tx.session.execute(
            text(
                "SELECT id, status, version, misstatement_id FROM proposed_entries "
                "WHERE work_item_id = :w AND id = ANY(:ids) ORDER BY id FOR UPDATE"
            ),
            {"w": work_item_id, "ids": list(entry_ids)},
        )
    ).mappings()
    found = [dict(r) for r in rows]
    if len(found) != len(set(entry_ids)):
        raise NotFound(TARGET)
    return found


async def _decide(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    entry_id: UUID,
    *,
    decision: str,
    seen_version: int,
    channel: Literal["app", "record"] = "app",
    batch_id: UUID | None = None,
    grant_id: UUID | None = None,
    reason_code: str | None = None,
    note: str | None = None,
    evidence_version_id: UUID | None = None,
) -> None:
    sealed = None if note is None else await seal(ctx.tenant_id, note.encode(), "adjustments.note")
    await tx.session.execute(
        text(
            "INSERT INTO proposed_entry_decisions (tenant_id, engagement_id, work_item_id, "
            "entry_id, decision, actor_principal, channel, reason_code, note_sealed, "
            "evidence_version_id, approval_batch_id, approval_grant_id, seen_version) VALUES "
            "(:t, :e, :w, :id, :d, 'firm_user', :ch, :r, :n, :ev, :b, :g, :v)"
        ),
        {
            "t": ctx.tenant_id,
            "e": engagement_id,
            "w": work_item_id,
            "id": entry_id,
            "d": decision,
            "ch": channel,
            "r": reason_code,
            "n": sealed,
            "ev": evidence_version_id,
            "b": batch_id,
            "g": grant_id,
            "v": seen_version,
        },
    )


async def _set_status(tx: UnitOfWork, entry_ids: Sequence[UUID], status: str) -> None:
    await tx.session.execute(
        text(
            "UPDATE proposed_entries SET status = :s, version = version + 1 WHERE id = ANY(:ids)"
        ),
        {"s": status, "ids": list(entry_ids)},
    )


async def _batch(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    entry_ids: Sequence[UUID],
    policy_version_id: UUID | None,
    label: str,
) -> UUID:
    return (
        await tx.session.execute(
            text(
                "INSERT INTO approval_batches (tenant_id, engagement_id, work_item_id, "
                "policy_version_id, entry_ids, approver_user_id, label) VALUES "
                "(:t, :e, :w, :p, :ids, :by, :label) RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "w": work_item_id,
                "p": policy_version_id,
                "ids": list(entry_ids),
                "by": ctx.user_id,
                "label": label,
            },
        )
    ).scalar_one()


def _check_versions(rows: Sequence[Mapping[str, object]], seen: Mapping[str, int]) -> None:
    for r in rows:
        if seen.get(str(r["id"])) != r["version"]:
            raise EntriesMoved(facts={"entry": str(r["id"])})


# --- the acts ------------------------------------------------------------------------------------


async def send(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    entry_ids: Sequence[UUID],
    recipient_contact_id: UUID,
    wording_template_version_id: UUID,
    seen_versions: Mapping[str, int],
    label: str,
) -> Sent:
    """`POST …/proposed-entries:approve-and-send` (the route authorised `SEND`)."""
    _live_human(ctx, SEND)
    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    not_before = await clock.now(ctx.tenant) + UNDO_WINDOW
    scope = Scope(engagement_id=engagement_id, work_item_id=work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        rows = await _locked_entries(tx, work_item_id, entry_ids)
        _check_versions(rows, seen_versions)
        if any(r["status"] not in _SENDABLE for r in rows):
            raise EntryNotSendable
        batch_id = await _batch(tx, ctx, engagement_id, work_item_id, entry_ids, None, label)
        grant_id = await issue_grant(
            tx,
            ctx,
            action=SEND,
            resource=ref.resource(),
            subject=Target(BATCH_TARGET, batch_id),
            payload_sha256=send_digest(
                batch_id, entry_ids, recipient_contact_id, wording_template_version_id
            ),
            not_before=not_before,
            expires_at=not_before + GRANT_LIFETIME,
        )
        for r in rows:
            await _decide(
                tx, ctx, engagement_id, work_item_id, UUID(str(r["id"])),
                decision="sent_to_client", seen_version=int(str(r["version"])),
                batch_id=batch_id, grant_id=grant_id,
            )  # fmt: skip
        await _set_status(tx, entry_ids, "approved")
        tx.record(
            "proposed_entries.sent_to_client",
            target=Target(BATCH_TARGET, batch_id),
            after=Ref(entries=len(rows), grant=grant_id),
            scope=scope,
        )
        tx.emit(
            EntriesSentToClient(
                approval_batch_id=batch_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                entry_ids=list(entry_ids),
                recipient_contact_id=recipient_contact_id,
                wording_template_version_id=wording_template_version_id,
            ),
            not_before=not_before,
            grant_id=grant_id,
        )
    return Sent(batch_id, not_before)


async def undo_send(ctx: AuthContext, work_item_id: UUID, batch_id: UUID) -> None:
    """Undo inside the window, by the approver: the grant voided, `send_undone` on each entry."""
    _live_human(ctx, SEND)
    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        found = (
            await tx.session.execute(
                text(
                    "SELECT b.entry_ids, b.approver_user_id, d.approval_grant_id "
                    "FROM approval_batches b JOIN proposed_entry_decisions d "
                    "ON d.approval_batch_id = b.id WHERE b.id = :b AND b.work_item_id = :w "
                    "LIMIT 1"
                ),
                {"b": batch_id, "w": work_item_id},
            )
        ).first()
        if found is None or found[1] != ctx.user_id:
            raise NotFound(BATCH_TARGET)
        if found[2] is None or not await void_grant(tx, found[2]):
            raise UndoWindowClosed
        rows = await _locked_entries(tx, work_item_id, found[0])
        for r in rows:
            await _decide(
                tx, ctx, engagement_id, work_item_id, UUID(str(r["id"])),
                decision="send_undone", seen_version=int(str(r["version"])), batch_id=batch_id,
            )  # fmt: skip
        await _set_status(tx, found[0], "review_required")
        tx.record(
            "proposed_entries.send_undone",
            target=Target(BATCH_TARGET, batch_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


async def create_batch(
    ctx: AuthContext,
    work_item_id: UUID,
    entry_ids: Sequence[UUID],
    policy_version_id: UUID,
    label: str,
) -> UUID:
    """`POST /v1/approval-batches` (`approval_batch.create`): within-threshold entries approved
    together by the named person ("Approved by Hannah Leclerc under BH AJE thresholds v2")."""
    _live_human(ctx, "approval_batch.create")
    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        rows = await _locked_entries(tx, work_item_id, entry_ids)
        if any(r["status"] not in _BATCHABLE for r in rows):
            raise EntryNotSendable
        batch_id = await _batch(
            tx, ctx, engagement_id, work_item_id, entry_ids, policy_version_id, label
        )
        for r in rows:
            await _decide(
                tx, ctx, engagement_id, work_item_id, UUID(str(r["id"])),
                decision="approved", seen_version=int(str(r["version"])), batch_id=batch_id,
            )  # fmt: skip
        await _set_status(tx, entry_ids, "approved")
        tx.record(
            "approval_batch.created",
            target=Target(BATCH_TARGET, batch_id),
            after=Ref(entries=len(rows)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return batch_id


async def reject(ctx: AuthContext, entry_id: UUID, reason_code: str) -> UUID:
    """`POST /v1/proposed-entries/{id}/reject` (`proposed_entry.reject`)."""
    _live_human(ctx, "proposed_entry.reject")
    return await _one(ctx, entry_id, "rejected", "rejected", _REJECTABLE, reason_code=reason_code)


async def record_client_decision(
    ctx: AuthContext,
    entry_id: UUID,
    *,
    decision: ClientDecision,
    reason: str | None,
    evidence_version_id: UUID,
) -> UUID:
    """Record mode (`proposed_entry.record_client_decision`): the client's decision from email,
    with the email as evidence; the owners' hooks follow in the same unit of work."""
    _live_human(ctx, "proposed_entry.record_client_decision")
    status = {"client_accepted": "client_approved", "client_declined": "client_declined"}.get(
        decision
    )
    return await _one(
        ctx, entry_id, decision, status, _RECORDABLE, channel="record", note=reason,
        evidence_version_id=evidence_version_id, client=decision,
    )  # fmt: skip


async def _one(
    ctx: AuthContext,
    entry_id: UUID,
    decision: str,
    status: str | None,
    allowed: frozenset[str],
    *,
    channel: Literal["app", "record"] = "app",
    reason_code: str | None = None,
    note: str | None = None,
    evidence_version_id: UUID | None = None,
    client: ClientDecision | None = None,
) -> UUID:
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, engagement_id, work_item_id, status, version, "
                        "misstatement_id FROM proposed_entries WHERE id = :id FOR UPDATE"
                    ),
                    {"id": entry_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound(TARGET)
        if row["status"] not in allowed:
            raise EntriesMoved(facts={"status": str(row["status"])})
        await lock_ref(tx, row["engagement_id"])
        await _decide(
            tx, ctx, row["engagement_id"], row["work_item_id"], entry_id, decision=decision,
            seen_version=row["version"], channel=channel, reason_code=reason_code, note=note,
            evidence_version_id=evidence_version_id,
        )  # fmt: skip
        if status is not None:
            await _set_status(tx, [entry_id], status)
        if client is not None:
            for hook in _HOOKS:
                await hook(tx, entry_id, row["misstatement_id"], client)
        tx.record(
            _AUDIT[decision],
            target=Target(TARGET, entry_id),
            scope=Scope(engagement_id=row["engagement_id"], work_item_id=row["work_item_id"]),
        )
    return entry_id
