"""Posting approved entries into the client's ledger (C-02-T18; SPEC-700; ADR-344; DEC-5704).
PROTECTED (red). The only caller of `integrations.api.execute_write` with the W1 capability
(POST-001).

- **Dry run** (`dry_run`): each entry through the writer's preflight (balanced, open period,
  mapped and active accounts); reads only, nothing is written.
- **Batch** (`create_batch`, `POST …/posting-batches`, fresh MFA, Idempotency-Key): a live person
  holding `posting_batch.post` on the engagement posts approved entries of a non-attest client.
  One `posting_batches` row (code `YYYY-MM-A`, the next letter for the period), the entries
  stamped with the batch, and a single-use approval grant over the payload hash (entries, lines,
  dates, closing date) with `not_before = +10 s`; the same Idempotency-Key answers the same batch.
  `PostingBatchWorkflow` (`posting:<tenant>:<batch>`, time sensitive) starts after commit.
- **Undo** (`undo_batch`): inside the hold the grant is voided and nothing is written.
- **Run** (`run_batch`, the workflow's activity): consumes the grant (the single gate, which
  re-checks the approver), re-reads ADR-344's switches through `execute_write`, then posts each
  entry once with the idempotency key `{batch}:{entry}` (an entry already posted by an earlier
  attempt is `already_posted`, never a second journal entry), records each result, sets the
  closing date once after the last entry, and emits `posting_batch.posted` (C-01's period lock).
  Every write is the approver's (the grant names them), never an agent's.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.adjustments.entries import engagement_of
from abacus.modules.adjustments.posting_errors import (
    ApprovalGrantMismatch,
    AttestClientPostingRefused,
    EntryLocked,
    PostingNotEnabled,
)
from abacus.modules.engagements.api import engagement_resource_of, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    consume_grant,
    is_synthetic_firm,
    issue_grant,
    member_context,
    void_grant,
)
from abacus.modules.integrations.api import (
    W1_CAPABILITY,
    ClosingDate,
    FakeQboTransport,
    JournalEntry,
    JournalLine,
    LogRow,
    Posted,
    PostingFacts,
    QboTransport,
    QuickBooksOnlineWriter,
    W1Evidence,
    W1Operation,
    W1Refused,
    W1Scope,
    WriteError,
    execute_write,
    register_posting_log,
    w1_ledger,
    w1_refusal,
)

ACTION: Final = "posting_batch.post"
SUBJECT: Final = "posting_batch"
HOLD: Final = timedelta(seconds=10)
GRANT_TTL: Final = timedelta(hours=1)
POSTABLE: Final = frozenset({"approved", "client_approved", "failed_post"})
LEDGER_LABEL: Final = "QuickBooks Online"
_LETTERS: Final = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class PostingBatchPosted(DomainEvent):
    """The batch's entries are in the client's ledger and its closing date is set (C-01 locks
    the period; CLS-11's log reads it)."""

    event_type: ClassVar[str] = "posting_batch.posted"

    batch_id: UUID
    work_item_id: UUID
    period: str
    closing_date: date | None


@dataclass(frozen=True)
class _Entry:
    id: UUID
    ref: str
    status: str
    version: int
    is_attest_client: bool
    txn_date: date
    lines: tuple[JournalLine, ...]
    amount: Decimal


@dataclass(frozen=True)
class _Scope:
    engagement_id: UUID
    client_id: UUID
    client_entity_id: UUID
    connection_id: UUID
    period: str
    period_end: date

    def w1(self) -> W1Scope:
        return W1Scope(
            self.client_id, self.client_entity_id, self.connection_id, self.engagement_id
        )


# --- the ledger's transport ----------------------------------------------------------------------

TransportFactory = Callable[[TenantContext, UUID], QboTransport | None]
_transports: list[TransportFactory] = []
_fakes: dict[tuple[UUID, UUID], FakeQboTransport] = {}


def register_qbo_transport(factory: TransportFactory) -> None:
    """The live QuickBooks transport for a connection (registered by the connector when the
    write path is released, ADR-344 §10). Until then only a synthetic firm posts, to the fake."""
    _transports[:] = [factory]


async def transport_for(tenant: TenantContext, connection_id: UUID) -> QboTransport:
    for factory in _transports:
        found = factory(tenant, connection_id)
        if found is not None:
            return found
    if not await is_synthetic_firm(tenant):
        raise W1Refused(facts={"reason": "write_capability_not_released"})
    return _fakes.setdefault((tenant.tenant_id, connection_id), FakeQboTransport())


# --- reads ---------------------------------------------------------------------------------------

_ENTRIES = text(
    "SELECT e.id, e.ref, e.status, e.version, e.is_attest_client, e.amount, e.txn_date, "
    "e.posting_batch_id, l.line_no, l.account_code, l.debit, l.credit "
    "FROM proposed_entries e JOIN proposed_entry_lines l ON l.entry_id = e.id "
    "WHERE e.work_item_id = :w AND e.id = ANY(:ids) ORDER BY e.kind, e.number, l.line_no"
)


async def _entries(tenant: TenantContext, work_item_id: UUID, ids: Sequence[UUID]) -> list[_Entry]:
    async with tenant_session(tenant) as session:
        rows = list((await session.execute(_ENTRIES, {"w": work_item_id, "ids": list(ids)})).all())
    out: dict[UUID, _Entry] = {}
    for r in rows:
        line = JournalLine(
            str(r.account_code),
            "Debit" if Decimal(r.debit) > 0 else "Credit",
            Decimal(r.debit) if Decimal(r.debit) > 0 else Decimal(r.credit),
        )
        found = out.get(r.id)
        if found is None:
            out[r.id] = _Entry(
                r.id, str(r.ref), str(r.status), int(r.version), bool(r.is_attest_client),
                cast(date, r.txn_date) if r.txn_date is not None else date.min,
                (line,), Decimal(r.amount),
            )  # fmt: skip
        else:
            out[r.id] = _Entry(
                found.id, found.ref, found.status, found.version, found.is_attest_client,
                found.txn_date, (*found.lines, line), found.amount,
            )  # fmt: skip
    if set(out) != set(ids):
        raise NotFound("proposed_entry")
    return [out[i] for i in ids]


async def _scope(ctx: AuthContext, work_item_id: UUID) -> _Scope:
    from abacus.modules.engagements.api import work_item_period

    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, engagement_id)
    ledger = await w1_ledger(ctx, ref.client_entity_id)
    if ledger.connection_id is None:
        raise PostingNotEnabled(facts={"reason": "no_ledger_connection"})
    if ledger.needs_reauth:  # C-02-T20: a forced 401 refuses posting everywhere
        raise W1Refused(facts={"reason": "connection_needs_reauth"})
    _, end = await work_item_period(ctx.tenant, work_item_id)
    if end is None:
        raise NotFound("work_item_period")
    period = f"{end.year:04d}-{end.month:02d}"
    return _Scope(engagement_id, ledger.client_id, ref.client_entity_id, ledger.connection_id,
                  period, end)  # fmt: skip


def _journal(e: _Entry, period_end: date) -> JournalEntry:
    return JournalEntry(e.ref, e.txn_date if e.txn_date != date.min else period_end, e.lines)


def _body(entry: JournalEntry) -> bytes:
    """A W1 request as stored write-once (the entry, its lines and date; no names)."""
    return json.dumps(
        {
            "doc_number": entry.doc_number,
            "txn_date": entry.txn_date.isoformat(),
            "lines": [[ln.account_ref, ln.posting_type, str(ln.amount)] for ln in entry.lines],
        },
        sort_keys=True,
    ).encode()


def _posted_evidence(p: Posted) -> W1Evidence:
    status = "failed" if p.error is not None else ("verified" if p.verified else "verify_mismatch")
    return W1Evidence(
        json.dumps({"external_ref": p.external_ref, "error": p.error}, sort_keys=True).encode(),
        json.dumps({"verified": p.verified}, sort_keys=True).encode(),
        p.external_ref or None,
        status,  # type: ignore[arg-type]  # the three words are WriteStatus's
    )


def _closing_evidence(error: WriteError | None) -> W1Evidence:
    body = json.dumps({"error": error}, sort_keys=True).encode()
    return W1Evidence(body, body, None, "failed" if error is not None else "verified")


def payload_digest(
    batch_code: str, period: str, closing_date: date | None, entries: Sequence[_Entry]
) -> str:
    """What the grant is bound to: the entries, their lines and dates, and the closing date."""
    body = {
        "batch": batch_code,
        "period": period,
        "closing_date": None if closing_date is None else closing_date.isoformat(),
        "entries": [
            {
                "id": str(e.id),
                "ref": e.ref,
                "version": e.version,
                "txn_date": e.txn_date.isoformat(),
                "lines": [[ln.account_ref, ln.posting_type, str(ln.amount)] for ln in e.lines],
            }
            for e in entries
        ],
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


# --- dry run -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DryRunResult:
    entry_id: UUID
    ok: bool
    failed_check: str | None
    account_ref: str | None


@dataclass(frozen=True)
class DryRun:
    entry_count: int
    total_amount: Decimal
    closing_date_target: date
    results: tuple[DryRunResult, ...]


_CHECK: Final = {
    "unbalanced": "balanced",
    "closed_period": "closing_date_unlocked",
    "unmapped_account": "mapped_accounts",
    "inactive_account": "active_accounts",
    "doc_number": "balanced",
}


async def dry_run(ctx: AuthContext, work_item_id: UUID, entry_ids: Sequence[UUID]) -> DryRun:
    """Preflight only; nothing is written (CLS-07 c2)."""
    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    await authorise(
        ctx, "posting_batch.dry_run", await engagement_resource_of(ctx.tenant, engagement_id)
    )
    scope = await _scope(ctx, work_item_id)
    entries = await _entries(ctx.tenant, work_item_id, entry_ids)
    writer = QuickBooksOnlineWriter(await transport_for(ctx.tenant, scope.connection_id))
    results = []
    for e in entries:
        check = await writer.preflight(_journal(e, scope.period_end))
        results.append(
            DryRunResult(
                e.id,
                check.ok,
                None if check.failed_check is None else _CHECK[check.failed_check],
                check.account_ref,
            )
        )
    total = sum((e.amount for e in entries), Decimal("0.00"))
    return DryRun(len(entries), total, scope.period_end, tuple(results))


# --- the batch -----------------------------------------------------------------------------------

_BATCH_BY_KEY = text("SELECT id FROM posting_batches WHERE idempotency_key = :k")
_CODES = text(
    "SELECT batch_code FROM posting_batches WHERE client_entity_id = :ce AND period = :p"
)
_NEW_BATCH = text(
    "INSERT INTO posting_batches (tenant_id, engagement_id, work_item_id, client_entity_id, "
    "connection_id, batch_code, period, entry_count, total_amount, closing_date_target, "
    "posted_by_user_id, idempotency_key) VALUES (:t, :e, :w, :ce, :c, :code, :p, :n, :total, "
    ":closing, :u, :k) RETURNING id"
)
_STAMP = text(
    "UPDATE proposed_entries SET posting_batch_id = :b, posting_target = 'client_ledger', "
    "version = version + 1 WHERE id = :id AND version = :v AND posting_batch_id IS NULL "
    "RETURNING id"
)
_GRANT = text("UPDATE posting_batches SET approval_grant_id = :g WHERE id = :b")


def next_code(period: str, taken: Sequence[str]) -> str:
    used = {c[-1] for c in taken}
    letter = next(ch for ch in _LETTERS if ch not in used)
    return f"{period}-{letter}"


@dataclass(frozen=True)
class Created:
    batch_id: UUID
    grant_id: UUID | None
    created: bool


async def create_batch(
    ctx: AuthContext,
    work_item_id: UUID,
    entry_ids: Sequence[UUID],
    seen_versions: dict[UUID, int],
    *,
    set_closing_date: bool,
    idempotency_key: str,
) -> Created:
    """The batch and its grant; the caller starts the workflow after commit (`workflow_id`)."""
    async with tenant_session(ctx.tenant) as session:
        again = await session.scalar(_BATCH_BY_KEY, {"k": idempotency_key})
    if again is not None:
        return Created(cast(UUID, again), None, False)
    scope = await _scope(ctx, work_item_id)
    resource = await engagement_resource_of(ctx.tenant, scope.engagement_id)
    await authorise(ctx, ACTION, resource)
    entries = await _entries(ctx.tenant, work_item_id, entry_ids)
    if any(e.is_attest_client for e in entries):
        raise AttestClientPostingRefused(facts={"reason": "attest_client"})
    for e in entries:
        if e.status not in POSTABLE:
            raise EntryLocked(facts={"entry_id": str(e.id), "status": e.status})
        if seen_versions.get(e.id) != e.version:
            raise ApprovalGrantMismatch(facts={"entry_id": str(e.id)})
    refusal = await w1_refusal(ctx.tenant, scope.w1())
    if refusal == "attest_client_posting_refused":
        raise AttestClientPostingRefused(facts={"reason": refusal})
    async with tenant_session(ctx.tenant) as session:
        taken = [
            str(c)
            for c in (
                await session.scalars(_CODES, {"ce": scope.client_entity_id, "p": scope.period})
            )
        ]
    code = next_code(scope.period, taken)
    closing = scope.period_end if set_closing_date else None
    digest = payload_digest(code, scope.period, closing, entries)
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        batch_id = cast(
            UUID,
            await tx.session.scalar(
                _NEW_BATCH,
                {
                    "t": ctx.tenant_id, "e": scope.engagement_id, "w": work_item_id,
                    "ce": scope.client_entity_id, "c": scope.connection_id, "code": code,
                    "p": scope.period, "n": len(entries),
                    "total": sum((e.amount for e in entries), Decimal("0.00")),
                    "closing": closing, "u": ctx.user_id, "k": idempotency_key,
                },
            ),
        )  # fmt: skip
        for e in entries:
            if (
                await tx.session.scalar(_STAMP, {"b": batch_id, "id": e.id, "v": e.version})
                is None
            ):
                raise ApprovalGrantMismatch(facts={"entry_id": str(e.id)})
        grant_id = await issue_grant(
            tx,
            ctx,
            action=ACTION,
            resource=resource,
            subject=Target(SUBJECT, batch_id),
            payload_sha256=digest,
            not_before=now + HOLD,
            expires_at=now + GRANT_TTL,
        )
        await tx.session.execute(_GRANT, {"g": grant_id, "b": batch_id})
        tx.record(
            "posting_batch.created",
            target=Target(SUBJECT, batch_id),
            after=Ref(entries=len(entries)),
            scope=Scope(engagement_id=scope.engagement_id),
        )
    return Created(batch_id, grant_id, True)


def workflow_id(tenant_id: UUID, batch_id: UUID) -> str:
    return f"posting:{tenant_id}:{batch_id}"


_BATCH = text(
    "SELECT id, engagement_id, work_item_id, client_entity_id, connection_id, batch_code, "
    "period, status, closing_date_target, closing_date_set_at, approval_grant_id, "
    "posted_by_user_id FROM posting_batches WHERE id = :b"
)


async def undo_batch(ctx: AuthContext, batch_id: UUID) -> None:
    """Inside the hold: the grant is voided, the entries released, nothing written."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_BATCH, {"b": batch_id})).first()
    if row is None or row.posted_by_user_id != ctx.user_id:
        raise NotFound(SUBJECT)
    async with uow(ctx.tenant) as tx:
        if row.approval_grant_id is None or not await void_grant(tx, row.approval_grant_id):
            raise ApprovalGrantMismatch(facts={"batch_id": str(batch_id)})
        await tx.session.execute(
            text(
                "UPDATE proposed_entries SET posting_batch_id = NULL, posting_target = NULL, "
                "version = version + 1 WHERE posting_batch_id = :b AND status <> 'posted'"
            ),
            {"b": batch_id},
        )
        tx.record("posting_batch.undone", target=Target(SUBJECT, batch_id))


# --- the run (PostingBatchWorkflow's activity) ---------------------------------------------------

_DONE = text(
    "SELECT proposed_entry_id, external_txn_id FROM posting_results "
    "WHERE posting_batch_id = :b AND outcome IN ('posted', 'already_posted')"
)
_ATTEMPTS = text(
    "SELECT coalesce(max(attempt_no), 0) FROM posting_results "
    "WHERE posting_batch_id = :b AND proposed_entry_id = :e"
)
_RESULT = text(
    "INSERT INTO posting_results (tenant_id, posting_batch_id, proposed_entry_id, attempt_no, "
    "outcome, external_txn_id, external_doc_number, provider_code, verified_at) VALUES (:t, :b, "
    ":e, :n, :o, :ext, :doc, :code, CASE WHEN :ext IS NULL THEN NULL ELSE clock_timestamp() END)"
)
_ENTRY_POSTED = text(
    "UPDATE proposed_entries SET status = :s, external_txn_ref = :ext, version = version + 1 "
    "WHERE id = :e"
)
_STATUS = text("UPDATE posting_batches SET status = :s, version = version + 1 WHERE id = :b")
_FINISH = text(
    "UPDATE posting_batches SET status = :s, posted_at = clock_timestamp(), "
    "first_external_ref = :first, last_external_ref = :last, failure_count = :failed, "
    "closing_date_set_at = CASE WHEN :closed THEN coalesce(closing_date_set_at, "
    "clock_timestamp()) ELSE closing_date_set_at END, version = version + 1 WHERE id = :b"
)
_CLOSING_EVENT = text(
    "INSERT INTO closing_date_events (tenant_id, client_entity_id, connection_id, period, "
    "closing_date, source, set_by_user_id, posting_batch_id) VALUES (:t, :ce, :c, :p, :d, "
    "'set_by_accrued', :u, :b)"
)
_ENTRY_IDS = text(
    "SELECT id FROM proposed_entries WHERE posting_batch_id = :b ORDER BY kind, number"
)


async def run_batch(tenant_id: UUID, batch_id: UUID) -> str:
    """Consume the grant, post each entry once, set the closing date once. Answers the batch's
    status; a replay or retry of a finished batch writes nothing more."""
    system = TenantContext(tenant_id, "system", f"posting_batch:{batch_id}")
    async with tenant_session(system) as session:
        row = (await session.execute(_BATCH, {"b": batch_id})).first()
        ids = [cast(UUID, i) for i in await session.scalars(_ENTRY_IDS, {"b": batch_id})]
        done = {
            cast(UUID, r[0]): str(r[1])
            for r in (await session.execute(_DONE, {"b": batch_id})).all()
        }
    if row is None:
        raise NotFound(SUBJECT)
    if row.status == "posted":
        return "posted"
    approver = cast(UUID, row.posted_by_user_id)
    acting = TenantContext(tenant_id, "system", system.actor_id, on_behalf_of_user_id=approver)
    entries = await _entries(acting, row.work_item_id, ids)
    period = str(row.period)
    year, month = (int(p) for p in period.split("-"))
    period_end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    digest = payload_digest(str(row.batch_code), period, row.closing_date_target, [
        _Entry(e.id, e.ref, e.status, e.version - 1, e.is_attest_client, e.txn_date, e.lines,
               e.amount) for e in entries
    ])  # fmt: skip  # stamped once at batch creation: the grant saw the version before the stamp
    if row.approval_grant_id is None or not await consume_grant(
        tenant_id, row.approval_grant_id, batch_id, digest
    ):
        raise ApprovalGrantMismatch(facts={"batch_id": str(batch_id)})
    if row.status == "proposed":
        async with uow(acting) as tx:
            await tx.session.execute(_STATUS, {"s": "posting", "b": batch_id})
            tx.record("posting_batch.posting", target=Target(SUBJECT, batch_id))
    approver_ctx = await member_context(tenant_id, approver)
    if approver_ctx is None:
        raise ApprovalGrantMismatch(facts={"batch_id": str(batch_id)})
    ledger = await w1_ledger(approver_ctx, row.client_entity_id)
    if ledger.needs_reauth:
        raise W1Refused(facts={"reason": "connection_needs_reauth"})
    client_id = ledger.client_id
    scope = W1Scope(client_id, row.client_entity_id, row.connection_id, row.engagement_id)
    writer = QuickBooksOnlineWriter(await transport_for(acting, row.connection_id))
    refs: list[str] = []
    failed = 0
    for e in entries:
        if e.id in done:
            refs.append(done[e.id])
            continue
        key = f"{batch_id}:{e.id}"

        async def post(entry: _Entry = e, request_id: str = key) -> Posted:
            return await writer.post(_journal(entry, period_end), request_id)

        posted = await execute_write(
            approver_ctx,
            W1_CAPABILITY,
            client_id,
            approval_ref=row.approval_grant_id,
            idempotency_key=key,
            w1=scope,
            perform=post,
            operation=W1Operation(
                "proposed_entry", e.id, "create_journal_entry", approver,
                _body(_journal(e, period_end)),
            ),
            evidence_of=_posted_evidence,
        )  # fmt: skip
        ok = posted.error is None and posted.verified
        async with uow(acting) as tx:
            attempt = int(await tx.session.scalar(_ATTEMPTS, {"b": batch_id, "e": e.id}) or 0) + 1
            await tx.session.execute(
                _RESULT,
                {
                    "t": tenant_id, "b": batch_id, "e": e.id, "n": attempt,
                    "o": "posted" if ok else "failed",
                    "ext": posted.external_ref if ok else None, "doc": e.ref,
                    "code": None if ok else (posted.error or "verify_mismatch"),
                },
            )  # fmt: skip
            await tx.session.execute(
                _ENTRY_POSTED,
                {
                    "s": "posted" if ok else "failed_post",
                    "ext": posted.external_ref or None,
                    "e": e.id,
                },
            )
            tx.record(
                "proposed_entry.posted" if ok else "proposed_entry.post_failed",
                target=Target("proposed_entry", e.id),
                after=Ref(batch=batch_id, attempt=attempt),
            )
        if ok:
            refs.append(posted.external_ref)
        else:
            failed += 1
    closed = False
    if failed == 0 and row.closing_date_target is not None and row.closing_date_set_at is None:

        async def close_books() -> WriteError | None:
            return await writer.set_book_close_date(row.closing_date_target, f"{batch_id}:closing")

        error = await execute_write(
            approver_ctx,
            W1_CAPABILITY,
            client_id,
            approval_ref=row.approval_grant_id,
            idempotency_key=f"{batch_id}:closing",
            w1=scope,
            perform=close_books,
            operation=W1Operation(
                SUBJECT, batch_id, "set_closing_date", approver,
                json.dumps({"closing_date": str(row.closing_date_target)}).encode(),
            ),
            evidence_of=_closing_evidence,
        )  # fmt: skip
        closed = error is None
    status = "posted" if failed == 0 else "failed_post"
    async with uow(acting) as tx:
        await tx.session.execute(
            _FINISH,
            {"s": status, "first": refs[0] if refs else None, "last": refs[-1] if refs else None,
             "failed": failed, "closed": closed, "b": batch_id},
        )  # fmt: skip
        if closed:
            await tx.session.execute(
                _CLOSING_EVENT,
                {"t": tenant_id, "ce": row.client_entity_id, "c": row.connection_id, "p": period,
                 "d": row.closing_date_target, "u": approver, "b": batch_id},
            )  # fmt: skip
        tx.record(f"posting_batch.{status}", target=Target(SUBJECT, batch_id))
        if status == "posted":
            tx.emit(
                PostingBatchPosted(
                    batch_id=batch_id,
                    work_item_id=row.work_item_id,
                    period=period,
                    closing_date=row.closing_date_target if closed else None,
                )
            )
    return status


__all__ = [
    "ACTION",
    "HOLD",
    "Created",
    "DryRun",
    "PostingBatchPosted",
    "batch_view",
    "create_batch",
    "dry_run",
    "entity_label",
    "next_code",
    "payload_digest",
    "register_qbo_transport",
    "run_batch",
    "transport_for",
    "undo_batch",
    "workflow_id",
]


async def entity_label(ctx: AuthContext, work_item_id: UUID) -> str:
    """The client entity's name for CLS-07 c2's confirm line ("… · Copperleaf Coffee Roasters")."""
    scope_ref = await get_ref(ctx, await engagement_of(ctx.tenant, work_item_id))
    return (await w1_ledger(ctx, scope_ref.client_entity_id)).entity_name


# --- the ledger console's provider (C-02-T20) ---------------------------------------------------

_LOG = text(
    "SELECT b.id, b.batch_code, b.period, b.status, b.entry_count, b.first_external_ref, "
    "b.last_external_ref, b.failure_count, b.resolved_failure_count, b.posted_at, "
    "b.posted_by_user_id, (SELECT count(*) FROM proposed_entries e "
    "WHERE e.posting_batch_id = b.id "
    "AND e.status IN ('approved', 'client_approved', 'posted')) AS approved "
    "FROM posting_batches b WHERE b.client_entity_id = :ce "
    "ORDER BY b.period DESC, b.batch_code DESC"
)
_PROPOSED = text(
    "SELECT count(*) FROM proposed_entries e JOIN posting_batches b ON b.id = e.posting_batch_id "
    "WHERE b.client_entity_id = :ce AND b.status = 'proposed'"
)
_CLOSING = text(
    "SELECT closing_date, set_by_user_id, at FROM closing_date_events "
    "WHERE client_entity_id = :ce ORDER BY at DESC, id DESC LIMIT 1"
)


async def posting_facts_for(tenant: TenantContext, client_entity_id: UUID) -> PostingFacts:
    """CLS-11's tiles, log and closing date for one entity (the caller authorised it)."""
    async with tenant_session(tenant) as session:
        rows = list((await session.execute(_LOG, {"ce": client_entity_id})).all())
        proposed = int(await session.scalar(_PROPOSED, {"ce": client_entity_id}) or 0)
        closing = (await session.execute(_CLOSING, {"ce": client_entity_id})).first()
    return PostingFacts(
        tuple(
            LogRow(r.id, r.batch_code, r.period, r.status, r.entry_count, int(r.approved),
                   r.first_external_ref, r.last_external_ref, r.resolved_failure_count,
                   r.failure_count, r.posted_at, r.posted_by_user_id)
            for r in rows
        ),
        proposed,
        None if closing is None else ClosingDate(closing.closing_date, closing.set_by_user_id,
                                                 closing.at),
    )  # fmt: skip


register_posting_log(posting_facts_for)


# --- views --------------------------------------------------------------------------------------

_BATCH_VIEW = text(
    "SELECT id, batch_code, period, status, entry_count, total_amount, first_external_ref, "
    "last_external_ref, closing_date_target, failure_count, resolved_failure_count, version, "
    "created_at FROM posting_batches WHERE id = :b"
)
_BATCH_ENTRIES = text(
    "SELECT e.id, e.ref, e.status, e.external_txn_ref, (SELECT r.provider_code FROM "
    "posting_results r WHERE r.proposed_entry_id = e.id AND r.posting_batch_id = :b "
    "ORDER BY r.attempt_no DESC LIMIT 1) AS failure FROM proposed_entries e "
    "WHERE e.posting_batch_id = :b ORDER BY e.kind, e.number"
)


async def batch_view(tenant: TenantContext, batch_id: UUID) -> dict[str, object]:
    """The batch as CLS-07's drawer and CLS-11's log read it (C8 v2 `PostingBatchOut`)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_BATCH_VIEW, {"b": batch_id})).mappings().first()
        entries = list((await session.execute(_BATCH_ENTRIES, {"b": batch_id})).mappings())
    if row is None:
        raise NotFound(SUBJECT)
    hold = cast(datetime, row["created_at"]) + HOLD
    return {
        "batch_id": row["id"],
        "batch_code": row["batch_code"],
        "period": row["period"],
        "status": row["status"],
        "entry_count": row["entry_count"],
        "total_amount": row["total_amount"],
        "first_external_ref": row["first_external_ref"],
        "last_external_ref": row["last_external_ref"],
        "closing_date_target": row["closing_date_target"],
        "failure_count": row["failure_count"],
        "resolved_failure_count": row["resolved_failure_count"],
        "undo_until": hold if row["status"] == "proposed" else None,
        "entries": [
            {
                "entry_id": e["id"],
                "ref": e["ref"],
                "status": e["status"],
                "external_txn_ref": e["external_txn_ref"],
                "failure": e["failure"] if e["status"] == "failed_post" else None,
            }
            for e in entries
        ],
        "version": row["version"],
    }


# --- the workflow's activity and start -----------------------------------------------------------

from temporalio import activity  # noqa: E402
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy  # noqa: E402

from abacus.kernel.dispatch import dispatch  # noqa: E402
from abacus.modules.adjustments.posting_types import RUN, PostingInput  # noqa: E402


@activity.defn(name=RUN)
async def run_posting_batch_activity(given: PostingInput) -> str:
    return await run_batch(UUID(given.tenant_id), UUID(given.batch_id))


ACTIVITIES = (run_posting_batch_activity,)


async def start_posting(tenant_id: UUID, batch_id: UUID) -> None:
    """Start the batch's workflow once (a replayed request keeps the running one)."""
    from abacus.modules.adjustments.posting_workflow import PostingBatchWorkflow

    await dispatch(
        PostingBatchWorkflow,
        PostingInput(str(tenant_id), str(batch_id)),
        id=workflow_id(tenant_id, batch_id),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
