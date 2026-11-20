"""Posting failures and conflicts (C-02-T24; SPEC-700 F3 US-3.2 to US-3.5; ADR-344; DEC-5816).
PROTECTED (red). Beside `posting.py`, the second caller of `integrations.api.execute_write` with
the W1 capability (POST-001); every write is still a person's, through a single-use grant.

- **A failed entry fails alone.** `run_batch` records `failed_post` with the writer's code. An
  inactive account (or any write error but the closing date) emits `posting_batch.failed`
  (C16 kind `posting_failed`: the poster and the entry's preparer); `closes` raises the CLS-06
  issue from it (adjustments never imports closes, BOUND-001).
- **Retry** (`retry_entry`, `POST …/posting-batches/{b}/entries/{e}/retry`, fresh MFA,
  Idempotency-Key): a new single-use grant over that one entry (`not_before = +10 s`) and the
  same `PostingBatchWorkflow` with the entry named. The activity re-reads the ledger through the
  writer's preflight and posts under the **same** idempotency key `{batch}:{entry}` (QuickBooks
  `requestid`), so an entry an earlier attempt did write answers its first id, never a second
  journal entry. When the last open entry posts, the closing date is set once, the batch reads
  Posted with "N failures resolved", and `posting_batch.posted` is emitted.
- **Closing-date conflicts.** An entry dated on or before the ledger's closing date is held
  `closing_date_locked` with one open `closing_date_conflicts` row; Retry is refused for it
  (409 `closing_date_conflict`). The two ways out: **ask the client** (the firm's
  `lift_closing_date_request` template row, sent by a person through `send_templated` with its
  scope check) or **re-date** (the approval is withdrawn, the date edited and the entry leaves
  the batch; it must be re-approved before it posts, because the payload hash changed).
- **Reversal carry.** `carry_reversals` (called by `closes` when the batch has posted and the next
  period's close exists): every posted entry with `reverses_on` gets one reversing entry on that
  close, `reversal_of_id` set, approved by the original approver's decision carried with its
  attribution ("Approved with AJE-01 by RM …"); it posts only when a person posts that batch.
- **Manual Reverse** (`reverse_entry`): a posted entry's reversal as a new proposed entry, to be
  approved and posted like any other (a new write, never a delete).
- **Export instead** (`export_file`): a deterministic JE import workbook of the approved entries
  (byte-identical for the same rows), and `record_external` marks an entry Recorded in ledger with
  evidence or a sync match.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.adjustments import posting as P
from abacus.modules.adjustments.entries import engagement_of, work_item_of
from abacus.modules.adjustments.posting_errors import ApprovalGrantMismatch, EntryLocked
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    consume_grant,
    issue_grant,
    member_context,
)
from abacus.modules.integrations.api import (
    W1_CAPABILITY,
    Posted,
    QuickBooksOnlineWriter,
    W1Operation,
    W1Refused,
    W1Scope,
    WriteError,
    execute_write,
    w1_ledger,
)

CONFLICT: Final = "closing_date_conflict"
LIFT_TEMPLATE: Final = "lift_closing_date_request"


class ClosingDateConflictOpen(DomainConflict):
    code = "closing_date_conflict"
    message = "The entry is dated on or before the ledger's closing date: ask the client or re-date."


class NotRetryable(DomainConflict):
    code = "entry_not_failed"
    message = "Only an entry that failed to post can be retried."


class PostingBatchFailed(DomainEvent):
    """C16 `posting_failed`: one or more entries of a batch failed for a reason other than the
    closing date. Identifiers only (DEC-60); `closes` raises the CLS-06 issue from it."""

    event_type: ClassVar[str] = "posting_batch.failed"

    posting_batch_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    entry_ids: Annotated[list[UUID], classified("internal")]
    posted_by_user_id: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


# --- failures inside the run ---------------------------------------------------------------------

_OPEN_CONFLICT = text(
    "INSERT INTO closing_date_conflicts (tenant_id, posting_batch_id, proposed_entry_id, "
    "ledger_closing_date, entry_date) SELECT :t, :b, :e, :closed, :d WHERE NOT EXISTS (SELECT 1 "
    "FROM closing_date_conflicts WHERE proposed_entry_id = :e AND status IN ('open', "
    "'client_asked')) RETURNING id"
)
_PREPARERS = text(
    "SELECT DISTINCT coalesce(e.on_behalf_of_user_id, CASE WHEN e.created_by_kind = 'human' "
    "THEN e.created_by_id::uuid END) FROM proposed_entries e WHERE e.id = ANY(:ids)"
)


async def record_failure(
    tx: object,
    *,
    tenant_id: UUID,
    batch_id: UUID,
    entry_id: UUID,
    entry_date: date,
    code: str,
    closed_on: date | None,
) -> bool:
    """Inside `run_batch`'s unit of work for a failed entry: a closing-date failure opens its
    conflict (one open per entry). Answers whether the failure is an issue (`posting_failed`)."""
    from abacus.kernel.uow import UnitOfWork

    unit = cast(UnitOfWork, tx)
    if code == "closing_date_locked" and closed_on is not None and entry_date <= closed_on:
        conflict = await unit.session.scalar(
            _OPEN_CONFLICT,
            {"t": tenant_id, "b": batch_id, "e": entry_id, "closed": closed_on, "d": entry_date},
        )
        if conflict is not None:
            unit.record(
                "closing_date_conflict.opened",
                target=Target(CONFLICT, cast(UUID, conflict)),
                after=Ref(entry_id=entry_id),
            )
        return False
    return True


async def failed_event(
    tenant: TenantContext,
    *,
    batch_id: UUID,
    work_item_id: UUID,
    posted_by: UUID,
    entry_ids: Sequence[UUID],
) -> PostingBatchFailed:
    async with tenant_session(tenant) as session:
        preparers = [
            cast(UUID, u)
            for u in await session.scalars(_PREPARERS, {"ids": list(entry_ids)})
            if u is not None
        ]
    return PostingBatchFailed(
        posting_batch_id=batch_id,
        work_item_id=work_item_id,
        entry_ids=list(entry_ids),
        posted_by_user_id=posted_by,
        recipient_user_ids=sorted({posted_by, *preparers}),
    )


@dataclass(frozen=True)
class FailedEntryFacts:
    """What CLS-06's issue says: the entry's ref, the writer's code and the ledger account the
    preflight named (the firm's account name, never provider text)."""

    work_item_id: UUID
    ref: str
    code: str
    account_name: str | None
    attempt: int


_FAILED_FACTS = text(
    "SELECT e.work_item_id, e.ref, r.provider_code, r.attempt_no FROM proposed_entries e JOIN "
    "posting_results r ON r.proposed_entry_id = e.id WHERE e.id = :e ORDER BY r.attempt_no DESC "
    "LIMIT 1"
)


async def failed_entry_facts(tenant: TenantContext, entry_id: UUID) -> FailedEntryFacts | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_FAILED_FACTS, {"e": entry_id})).first()
        if row is None:
            return None
        name = await session.scalar(
            text(
                "SELECT l.account_name FROM proposed_entry_lines l WHERE l.entry_id = :e "
                "ORDER BY l.line_no LIMIT 1"
            ),
            {"e": entry_id},
        )
    return FailedEntryFacts(
        cast(UUID, row.work_item_id), str(row.ref), str(row.provider_code or "provider_error"),
        None if name is None else str(name), int(row.attempt_no),
    )  # fmt: skip


def failure_line(facts: FailedEntryFacts) -> str:
    """CLS-07e's red line, from codes: "QuickBooks Online: account 'Accumulated Depreciation' is
    inactive"."""
    if facts.code == "inactive_account" and facts.account_name:
        return f"QuickBooks Online: account '{facts.account_name}' is inactive"
    words = {
        "inactive_account": "an account is inactive",
        "rate_limited": "QuickBooks Online is busy; retry in a minute",
        "needs_reauth": "the connection needs to be reconnected",
        "verify_mismatch": "the entry read back differently from what was sent",
    }
    return f"QuickBooks Online: {words.get(facts.code, 'the entry could not be posted')}"


# --- retry ---------------------------------------------------------------------------------------

_BATCH_ROW = text(
    "SELECT id, engagement_id, work_item_id, client_entity_id, connection_id, batch_code, "
    "period, status, closing_date_target, closing_date_set_at, posted_by_user_id, "
    "failure_count, resolved_failure_count FROM posting_batches WHERE id = :b"
)


def _single_digest(batch_code: str, period: str, entry: P._Entry) -> str:  # pyright: ignore[reportPrivateUsage]
    """A retry's grant covers one entry (no closing date: that is set once all have posted)."""
    return P.payload_digest(f"{batch_code}:retry:{entry.id}", period, None, [entry])


@dataclass(frozen=True)
class Retried:
    batch_id: UUID
    entry_id: UUID
    grant_id: UUID
    attempt: int


async def retry_entry(
    ctx: AuthContext, batch_id: UUID, entry_id: UUID, *, idempotency_key: str
) -> Retried:
    """A new grant over one failed entry; the caller starts the workflow (`start_retry`)."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_BATCH_ROW, {"b": batch_id})).first()
        conflict = await session.scalar(
            text(
                "SELECT id FROM closing_date_conflicts WHERE proposed_entry_id = :e "
                "AND status IN ('open', 'client_asked')"
            ),
            {"e": entry_id},
        )
        attempts = int(await session.scalar(P._ATTEMPTS, {"b": batch_id, "e": entry_id}) or 0)  # pyright: ignore[reportPrivateUsage]
    if row is None:
        raise NotFound(P.SUBJECT)
    resource = await engagement_resource_of(ctx.tenant, row.engagement_id)
    await authorise(ctx, P.ACTION, resource)
    (entry,) = await P._entries(ctx.tenant, row.work_item_id, [entry_id])  # pyright: ignore[reportPrivateUsage]
    if entry.status != "failed_post":
        raise NotRetryable(facts={"status": entry.status})
    if conflict is not None:
        raise ClosingDateConflictOpen(facts={"conflict_id": str(conflict)})
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        grant_id = await issue_grant(
            tx,
            ctx,
            action=P.ACTION,
            resource=resource,
            subject=Target(P.SUBJECT, batch_id),
            payload_sha256=_single_digest(str(row.batch_code), str(row.period), entry),
            not_before=now + P.HOLD,
            expires_at=now + P.GRANT_TTL,
        )
        tx.record(
            "posting_batch.retry_requested",
            target=Target(P.SUBJECT, batch_id),
            after=Ref(entry_id=entry_id, attempt=attempts + 1),
            scope=Scope(engagement_id=row.engagement_id),
        )
    return Retried(batch_id, entry_id, grant_id, attempts + 1)


def retry_workflow_id(tenant_id: UUID, retried: Retried) -> str:
    return f"posting:{tenant_id}:{retried.batch_id}:retry:{retried.entry_id}:{retried.attempt}"


async def run_retry(tenant_id: UUID, batch_id: UUID, entry_id: UUID, grant_id: UUID) -> str:
    """The retry's activity: consume the one-entry grant, re-read, post under the same key, then
    finish the batch if nothing is left open."""
    system = TenantContext(tenant_id, "system", f"posting_batch:{batch_id}")
    async with tenant_session(system) as session:
        row = (await session.execute(_BATCH_ROW, {"b": batch_id})).first()
    if row is None:
        raise NotFound(P.SUBJECT)
    approver = cast(UUID, row.posted_by_user_id)
    acting = TenantContext(tenant_id, "system", system.actor_id, on_behalf_of_user_id=approver)
    (entry,) = await P._entries(acting, row.work_item_id, [entry_id])  # pyright: ignore[reportPrivateUsage]
    if entry.status == "posted":
        return "posted"  # an earlier attempt of this retry already finished
    if not await consume_grant(
        tenant_id, grant_id, batch_id, _single_digest(str(row.batch_code), str(row.period), entry)
    ):
        raise ApprovalGrantMismatch(facts={"batch_id": str(batch_id)})
    approver_ctx = await member_context(tenant_id, approver)
    if approver_ctx is None:
        raise ApprovalGrantMismatch(facts={"batch_id": str(batch_id)})
    ledger = await w1_ledger(approver_ctx, row.client_entity_id)
    if ledger.needs_reauth:
        raise W1Refused(facts={"reason": "connection_needs_reauth"})
    scope = W1Scope(ledger.client_id, row.client_entity_id, row.connection_id, row.engagement_id)
    writer = QuickBooksOnlineWriter(await P.transport_for(acting, row.connection_id))
    period = str(row.period)
    year, month = (int(p) for p in period.split("-"))
    period_end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    key = f"{batch_id}:{entry_id}"  # the same key as the first attempt: never a second entry
    journal = P._journal(entry, period_end)  # pyright: ignore[reportPrivateUsage]

    async def post() -> Posted:
        return await writer.post(journal, key)

    posted = await execute_write(
        approver_ctx, W1_CAPABILITY, ledger.client_id, approval_ref=grant_id,
        idempotency_key=key, w1=scope, perform=post,
        operation=W1Operation(
            "proposed_entry", entry_id, "create_journal_entry", approver, P._body(journal)  # pyright: ignore[reportPrivateUsage]
        ),
        evidence_of=P._posted_evidence,  # pyright: ignore[reportPrivateUsage]
    )  # fmt: skip
    ok = posted.error is None and posted.verified
    closed_on = await writer.book_close_date() if not ok else None
    async with uow(acting) as tx:
        attempt = int(await tx.session.scalar(P._ATTEMPTS, {"b": batch_id, "e": entry_id}) or 0) + 1  # pyright: ignore[reportPrivateUsage]
        await tx.session.execute(
            P._RESULT,  # pyright: ignore[reportPrivateUsage]
            {
                "t": tenant_id, "b": batch_id, "e": entry_id, "n": attempt,
                "o": "posted" if ok else "failed",
                "ext": posted.external_ref if ok else None, "doc": entry.ref,
                "code": None if ok else (posted.error or "verify_mismatch"),
            },
        )  # fmt: skip
        await tx.session.execute(
            P._ENTRY_POSTED,  # pyright: ignore[reportPrivateUsage]
            {"s": "posted" if ok else "failed_post", "ext": posted.external_ref or None, "e": entry_id},
        )
        tx.record(
            "proposed_entry.posted" if ok else "proposed_entry.post_failed",
            target=Target("proposed_entry", entry_id),
            after=Ref(batch=batch_id, attempt=attempt),
        )
        if ok:
            await tx.session.execute(
                text(
                    "UPDATE posting_batches SET resolved_failure_count = least(failure_count, "
                    "resolved_failure_count + 1), version = version + 1 WHERE id = :b"
                ),
                {"b": batch_id},
            )
        elif await record_failure(
            tx, tenant_id=tenant_id, batch_id=batch_id, entry_id=entry_id,
            entry_date=journal.txn_date, code=posted.error or "verify_mismatch", closed_on=closed_on,
        ):  # fmt: skip
            tx.emit(
                await failed_event(
                    acting, batch_id=batch_id, work_item_id=row.work_item_id,
                    posted_by=approver, entry_ids=[entry_id],
                )
            )  # fmt: skip
    return await finish_if_done(tenant_id, batch_id, writer, approver_ctx, scope, grant_id)


_OPEN_IN_BATCH = text(
    "SELECT count(*) FROM proposed_entries WHERE posting_batch_id = :b AND status <> 'posted'"
)
_REFS = text(
    "SELECT external_txn_ref FROM proposed_entries WHERE posting_batch_id = :b AND status = "
    "'posted' ORDER BY kind, number"
)


async def finish_if_done(
    tenant_id: UUID,
    batch_id: UUID,
    writer: QuickBooksOnlineWriter,
    approver_ctx: AuthContext,
    scope: W1Scope,
    grant_id: UUID,
) -> str:
    """Once no entry of the batch is open: the closing date is set once and the batch posts."""
    system = TenantContext(tenant_id, "system", f"posting_batch:{batch_id}")
    async with tenant_session(system) as session:
        row = (await session.execute(_BATCH_ROW, {"b": batch_id})).first()
        open_left = int(await session.scalar(_OPEN_IN_BATCH, {"b": batch_id}) or 0)
        refs = [str(r) for r in await session.scalars(_REFS, {"b": batch_id}) if r is not None]
    if row is None:
        raise NotFound(P.SUBJECT)
    if open_left:
        return "failed_post"
    if row.status == "posted":
        return "posted"
    approver = cast(UUID, row.posted_by_user_id)
    closed = row.closing_date_set_at is not None
    if row.closing_date_target is not None and not closed:

        async def close_books() -> WriteError | None:
            return await writer.set_book_close_date(row.closing_date_target, f"{batch_id}:closing")

        error = await execute_write(
            approver_ctx, W1_CAPABILITY, scope.client_id, approval_ref=grant_id,
            idempotency_key=f"{batch_id}:closing", w1=scope, perform=close_books,
            operation=W1Operation(
                P.SUBJECT, batch_id, "set_closing_date", approver,
                json.dumps({"closing_date": str(row.closing_date_target)}).encode(),
            ),
            evidence_of=P._closing_evidence,  # pyright: ignore[reportPrivateUsage]
        )  # fmt: skip
        closed = error is None
    acting = TenantContext(tenant_id, "system", system.actor_id, on_behalf_of_user_id=approver)
    async with uow(acting) as tx:
        await tx.session.execute(
            text(
                "UPDATE posting_batches SET status = 'posted', posted_at = clock_timestamp(), "
                "first_external_ref = :first, last_external_ref = :last, closing_date_set_at = "
                "CASE WHEN :closed THEN coalesce(closing_date_set_at, clock_timestamp()) ELSE "
                "closing_date_set_at END, version = version + 1 WHERE id = :b"
            ),
            {"first": refs[0] if refs else None, "last": refs[-1] if refs else None,
             "closed": closed, "b": batch_id},
        )  # fmt: skip
        if closed and row.closing_date_set_at is None and row.closing_date_target is not None:
            await tx.session.execute(
                P._CLOSING_EVENT,  # pyright: ignore[reportPrivateUsage]
                {"t": tenant_id, "ce": row.client_entity_id, "c": row.connection_id,
                 "p": row.period, "d": row.closing_date_target, "u": approver, "b": batch_id},
            )  # fmt: skip
        tx.record("posting_batch.posted", target=Target(P.SUBJECT, batch_id))
        tx.emit(
            P.PostingBatchPosted(
                batch_id=batch_id,
                work_item_id=row.work_item_id,
                period=str(row.period),
                closing_date=row.closing_date_target if closed else None,
            )
        )
    return "posted"


# --- closing-date conflicts ----------------------------------------------------------------------

_CONFLICT_ROW = text(
    "SELECT c.id, c.posting_batch_id, c.proposed_entry_id, c.ledger_closing_date, c.entry_date, "
    "c.status, c.communication_ref, c.resolved_at, b.engagement_id, b.work_item_id, "
    "b.client_entity_id FROM closing_date_conflicts c JOIN posting_batches b ON b.id = "
    "c.posting_batch_id WHERE c.id = :c"
)


@dataclass(frozen=True)
class ConflictView:
    conflict_id: UUID
    entry_id: UUID
    ledger_closing_date: date
    entry_date: date
    status: str
    client_asked_at: object


async def conflict_view(tenant: TenantContext, conflict_id: UUID) -> ConflictView:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_CONFLICT_ROW, {"c": conflict_id})).first()
    if row is None:
        raise NotFound(CONFLICT)
    asked = None
    if row.communication_ref is not None:
        async with tenant_session(tenant) as session:
            asked = await session.scalar(
                text(
                    "SELECT created_at FROM audit_events WHERE action = "
                    "'closing_date_conflict.client_asked' AND target_id = :c ORDER BY created_at "
                    "LIMIT 1"
                ),
                {"c": conflict_id},
            )
    return ConflictView(
        row.id, row.proposed_entry_id, row.ledger_closing_date, row.entry_date, str(row.status),
        asked,
    )  # fmt: skip


async def ask_client(ctx: AuthContext, conflict_id: UUID) -> ConflictView:
    """The firm's "Lift closing date request" row to the client's approver of record, sent by
    this person through `send_templated` (its lint and scope check); never model text."""
    from abacus.modules.communications.api import RecipientRef, SendScope, send_templated
    from abacus.modules.engagements.api import client_contact_names, engagement_contacts
    from abacus.modules.identity.api import firm_name

    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_CONFLICT_ROW, {"c": conflict_id})).first()
    if row is None:
        raise NotFound(CONFLICT)
    await authorise(
        ctx, "closing_date_conflict.resolve",
        await engagement_resource_of(ctx.tenant, row.engagement_id),
    )  # fmt: skip
    if row.status != "open":
        raise DomainConflict(facts={"status": str(row.status)})
    contact = next(
        (
            c.contact_id
            for c in await engagement_contacts(ctx, row.engagement_id)
            if c.designation == "approver_of_record"
        ),
        None,
    )
    if contact is None:
        raise NotFound("approver_of_record")
    names = await client_contact_names(ctx.tenant, row.engagement_id, [contact])
    first = (names.get(contact) or "").split(" ")[0] or "there"
    closing = cast(date, row.ledger_closing_date)
    outcome = await send_templated(
        ctx,
        LIFT_TEMPLATE,
        RecipientRef("contact", contact),
        {
            "client_first_name": first,
            "firm_name": await firm_name(ctx.tenant_id),
            "connection_name": P.LEDGER_LABEL,
            "due_date": f"{closing:%b} {closing.day}, {closing.year}",
        },
        scope=SendScope(row.engagement_id),
        idempotency_key=f"{CONFLICT}:{conflict_id}",
    )
    if outcome.status == "blocked":
        raise DomainConflict(facts={"reason": str(outcome.blocked_reason)})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE closing_date_conflicts SET status = 'client_asked', communication_ref = :m "
                "WHERE id = :c AND status = 'open'"
            ),
            {"m": outcome.message_id, "c": conflict_id},
        )
        tx.record(
            "closing_date_conflict.client_asked",
            target=Target(CONFLICT, conflict_id),
            after=Ref(message_id=outcome.message_id),
            scope=Scope(engagement_id=row.engagement_id),
        )
    return await conflict_view(ctx.tenant, conflict_id)


async def redate(ctx: AuthContext, conflict_id: UUID, new_date: date, reason: str) -> ConflictView:
    """Withdraw the approval, edit the date and take the entry out of the batch: it must be
    re-approved (its payload hash changed) and posted in a new batch."""
    from abacus.modules.adjustments.close_approvals import redate_withdraw

    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_CONFLICT_ROW, {"c": conflict_id})).first()
    if row is None:
        raise NotFound(CONFLICT)
    await authorise(
        ctx, "closing_date_conflict.resolve",
        await engagement_resource_of(ctx.tenant, row.engagement_id),
    )  # fmt: skip
    if row.status not in ("open", "client_asked"):
        raise DomainConflict(facts={"status": str(row.status)})
    if new_date <= row.ledger_closing_date:
        raise DomainConflict(facts={"reason": "still_on_or_before_closing_date"})
    await redate_withdraw(ctx, row.proposed_entry_id, new_date, reason, conflict_id=conflict_id)
    return await conflict_view(ctx.tenant, conflict_id)


# --- reversals -----------------------------------------------------------------------------------

_REVERSIBLE = text(
    "SELECT e.id FROM proposed_entries e WHERE e.posting_batch_id = :b AND e.status = 'posted' "
    "AND e.reverses_on IS NOT NULL AND NOT EXISTS (SELECT 1 FROM proposed_entries r WHERE "
    "r.reversal_of_id = e.id) ORDER BY e.kind, e.number"
)


async def carry_reversals(tenant: TenantContext, batch_id: UUID, next_work_item_id: UUID) -> int:
    """Each posted entry of the batch with `reverses_on` gets one reversing entry on the next
    period's close, approved with the original's decision (attribution carried), never posted
    by a timer. Idempotent: an entry already reversed is skipped."""
    from abacus.modules.adjustments.close_approvals import carry_reversal

    async with tenant_session(tenant) as session:
        ids = [cast(UUID, i) for i in await session.scalars(_REVERSIBLE, {"b": batch_id})]
    for entry_id in ids:
        await carry_reversal(tenant, entry_id, next_work_item_id)
    return len(ids)


async def posted_batches_of(tenant: TenantContext, work_item_id: UUID) -> list[UUID]:
    """The close's posted batches (for a newly created next close to carry reversals from)."""
    async with tenant_session(tenant) as session:
        return [
            cast(UUID, b)
            for b in await session.scalars(
                text(
                    "SELECT id FROM posting_batches WHERE work_item_id = :w AND status = 'posted' "
                    "ORDER BY batch_code"
                ),
                {"w": work_item_id},
            )
        ]


async def reverse_entry(ctx: AuthContext, entry_id: UUID, on: date | None = None) -> UUID:
    """Manual Reverse: a posted entry's reversal as a new proposed entry on the same close
    (lines swapped, `reversal_of_id` set), approved and posted like any other."""
    from abacus.modules.adjustments.close_approvals import propose_reversal

    work_item_id = await work_item_of(ctx.tenant, entry_id)
    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    await authorise(
        ctx, "proposed_entry.create", await engagement_resource_of(ctx.tenant, engagement_id)
    )
    async with tenant_session(ctx.tenant) as session:
        status = await session.scalar(
            text("SELECT status FROM proposed_entries WHERE id = :e"), {"e": entry_id}
        )
        already = await session.scalar(
            text("SELECT id FROM proposed_entries WHERE reversal_of_id = :e"), {"e": entry_id}
        )
    if status != "posted":
        raise EntryLocked(facts={"status": str(status)})
    if already is not None:
        raise DomainConflict(facts={"reason": "already_reversed", "entry_id": str(already)})
    return await propose_reversal(ctx, entry_id, on)


# --- export instead ------------------------------------------------------------------------------

_EXPORT = text(
    "SELECT e.ref, coalesce(e.txn_date, :end) AS txn_date, l.line_no, l.account_code, "
    "l.account_name, l.debit, l.credit FROM proposed_entries e JOIN proposed_entry_lines l ON "
    "l.entry_id = e.id WHERE e.work_item_id = :w AND e.status IN ('approved', 'client_approved') "
    "AND e.posting_target IS DISTINCT FROM 'client_ledger' ORDER BY e.kind, e.number, l.line_no"
)
EXPORT_HEADER: Final = ("Journal No", "Journal Date", "Account", "Account Name", "Debits", "Credits")


async def export_file(ctx: AuthContext, work_item_id: UUID) -> bytes:
    """The JE import workbook (QuickBooks' Journal Entry import columns) of the approved, unposted
    entries: deterministic (the same rows give the same bytes), client text escaped by
    `safe_xlsx`; audited as `proposed_entry.exported`."""
    from abacus.modules.engagements.api import work_item_period

    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    await authorise(
        ctx, "proposed_entry.export", await engagement_resource_of(ctx.tenant, engagement_id)
    )
    _, end = await work_item_period(ctx.tenant, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(_EXPORT, {"w": work_item_id, "end": end})).all())
    body: list[tuple[str, ...]] = [EXPORT_HEADER]
    for r in rows:
        debit, credit = Decimal(r.debit), Decimal(r.credit)
        body.append(
            (
                str(r.ref), cast(date, r.txn_date).strftime("%m/%d/%Y"), str(r.account_code),
                str(r.account_name), f"{debit:.2f}" if debit else "", f"{credit:.2f}" if credit else "",
            )
        )  # fmt: skip
    content = workbook([Sheet("Journal entries", body)])
    async with uow(ctx.tenant) as tx:
        tx.record(
            "proposed_entry.exported",
            target=Target("work_item", work_item_id),
            after=Ref(rows=len(rows)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return content


async def record_external(
    ctx: AuthContext, entry_id: UUID, *, evidence_version_id: UUID | None, match_ref: str | None
) -> UUID:
    """Recorded in ledger (export path): evidence or a sync match, at least one; a person only."""
    from abacus.modules.adjustments.close_approvals import mark_recorded_externally

    if evidence_version_id is None and not match_ref:
        raise DomainConflict(facts={"reason": "evidence_or_match_required"})
    return await mark_recorded_externally(
        ctx, entry_id, evidence_version_id=evidence_version_id, match_ref=match_ref
    )


__all__ = [
    "LIFT_TEMPLATE",
    "ClosingDateConflictOpen",
    "ConflictView",
    "FailedEntryFacts",
    "NotRetryable",
    "PostingBatchFailed",
    "Retried",
    "ask_client",
    "posted_batches_of",
    "carry_reversals",
    "conflict_view",
    "export_file",
    "failed_entry_facts",
    "failure_line",
    "record_external",
    "record_failure",
    "redate",
    "retry_entry",
    "retry_workflow_id",
    "reverse_entry",
    "run_retry",
]

