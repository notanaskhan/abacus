"""N-04-T16: the notice response, part 2 (NOT-03; N-04 US-3.2, US-5; DEC-2311).

- **Send for signature.** A C7 draft envelope (`notice_response`) carrying the letter rendered
  through C11 and the cited enclosures. Refused until the partner's sign-off holds.
- **Readiness.** Ready to send only when the envelope is complete and any payment confirmation is
  accepted. A notice never reaches Sent unless the taxpayers signed (R-07, a property test).
- **Mark sent.** A person's record: the confirmation is sealed with its last four, the follow-up is
  the sent date plus the days (Sep 17 + 60 = Nov 16), and Sent moves to Awaiting IRS in one unit of
  work. No route calls an agency: the firm sends through DUT, fax or mail.
- **Agency replies.** A person's insert-only record: resolved closes, escalated escalates.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.clock import today
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch, signal_workflow
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.evidence.api import version_view
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices.events import (
    NoticeCreated,
    NoticeFollowUpDue,
    NoticeRespondBySoon,
    NoticeResponseReadyToSend,
    NoticeResponseSent,
)
from abacus.modules.notices.response import signoff_ready
from abacus.modules.notices.response_workflow import NoticeResponseWorkflow
from abacus.modules.notices.response_workflow_types import (
    AlertInput,
    FollowUpInput,
    NoticeResponseInput,
)
from abacus.modules.notices.service import Notice, move, notice
from abacus.modules.organisations.api import client_of_entity
from abacus.modules.reporting import api as c11
from abacus.modules.requests.api import NewRequestItem, add_request_item, items_of_version
from abacus.modules.signatures.api import (
    EnvelopeSource,
    SourceDocument,
    SourceDraft,
    SourceSigner,
    create_draft,
    envelope_status,
    envelope_summary_for,
    register_envelope_source,
)

SOURCE: Final = "notice_response"
APPROVAL_KIND: Final = "notice_response_sign_off"
CONFIRMATION_ITEM: Final = "confirmation_request_item_id"
CONFIRMATION_REQUEST: Final = "Upload your IRS payment confirmation"  # NOT-03c, verbatim
RECORD_TYPE: Final = "notice_response"
JsonRow = dict[str, Any]  # Any: rows and JSON columns as stored


class NotReady(DomainConflict):
    """Facts name what blocks the step (`facts.blocking`)."""

    code = "not_ready"


class LetterRendering(DomainConflict):
    """The letter's draft is rendering; send again once it is ready."""

    code = "letter_rendering"


def workflow_id(tenant_id: UUID, work_item_id: UUID) -> str:
    return f"notice_response:{tenant_id}:{work_item_id}"


async def on_notice_created(event: OutboxEvent) -> None:
    """Create notice committed: the respond-by alerts and the follow-up timer. Through the outbox,
    so Temporal being down delays them and never fails or loses the person's write."""
    work_item_id = UUID(str(event.payload["work_item_id"]))
    tenant = TenantContext(event.tenant_id, "system", "notices:timers")
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text("SELECT respond_by, notice_type_key FROM notices WHERE work_item_id = :w"),
                {"w": work_item_id},
            )
        ).first()
    if row is None:
        return
    await dispatch(
        NoticeResponseWorkflow,
        NoticeResponseInput(
            str(event.tenant_id), str(work_item_id),
            row.respond_by.isoformat() if row.respond_by else None,
            row.notice_type_key or "unknown",
        ),
        id=workflow_id(event.tenant_id, work_item_id),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )  # fmt: skip


async def _response_row(tenant: TenantContext, work_item_id: UUID) -> JsonRow:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT id, current_version_id, enclosures, payment, "
                        "signer_contact_ids, channel, follow_up_days, envelope_id, "
                        "generated_document_id, template_version_id, row_version "
                        "FROM notice_responses WHERE work_item_id = :w"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound("notice_response")
    return dict(row)


# --- the letter (C11, DEC-2311: the provider now carries the tenant) --------


async def letter_variables(
    tenant: TenantContext, owner: c11.OwnerRef, scope: c11.RenderScope
) -> Mapping[str, str]:
    """Typed variables by code: the notice's facts and the analysis's figures, never a model's."""
    del scope
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT n.notice_code, n.tax_year, n.position FROM notice_responses r JOIN "
                    "notices n ON n.tenant_id = r.tenant_id AND n.work_item_id = r.work_item_id "
                    "WHERE r.id = :r"
                ),
                {"r": owner.id},
            )
        ).first()
        analysis = (
            await session.execute(
                text(
                    "SELECT a.rows FROM notice_analyses a JOIN notice_responses r ON "
                    "r.tenant_id = a.tenant_id AND r.work_item_id = a.work_item_id "
                    "WHERE r.id = :r AND a.status = 'ready' ORDER BY a.version DESC LIMIT 1"
                ),
                {"r": owner.id},
            )
        ).scalar()
    if row is None:
        return {}
    values = {
        "notice_code": row.notice_code or "",
        "tax_year": "" if row.tax_year is None else str(row.tax_year),
        "position": row.position or "",
    }
    for figure in cast(list[JsonRow], analysis or []):
        values[f"{figure['key']}.irs"] = figure["irs"]
        values[f"{figure['key']}.difference"] = figure["difference"]
    return values


# The sign-off the sender is acting on, in this call: no other caller can render a letter final.
_approving: ContextVar[tuple[c11.ApprovalRef, UUID] | None] = ContextVar(
    "abacus_notice_letter_approval", default=None
)


async def _letter_approval(ref: c11.ApprovalRef) -> tuple[UUID, str] | None:
    held = _approving.get()
    return None if held is None or held[0] != ref else (held[1], ref.content_hash)


def register() -> None:
    """At import (notices/api.py): the C11 kind and the C7 source."""
    try:
        c11.document_kind(SOURCE)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=SOURCE,
                layout="notice_response",
                variables_provider=_no_variables,
                tenant_variables_provider=letter_variables,
                approval_provider=_letter_approval,
                retention_record_type=RECORD_TYPE,
            )
        )
    register_envelope_source(
        EnvelopeSource(
            kind=SOURCE,
            documents=_none,
            signers=_none,
            retention_record_type=RECORD_TYPE,
            gate="notice_response_send",
            completed_label="Signed",
            draft=_draft_source,
        )
    )


async def _no_variables(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
    del owner, scope
    return {}


async def _none(ctx: AuthContext, source_id: UUID) -> list[object]:
    del ctx, source_id
    return []


async def _enclosures(row: JsonRow) -> tuple[SourceDocument, ...]:
    out: list[SourceDocument] = []
    for enclosure in cast(list[JsonRow], row["enclosures"] or []):
        if enclosure.get("evidence_version_id") and enclosure.get("sha256"):
            out.append(
                SourceDocument(
                    sha256=str(enclosure["sha256"]),
                    evidence_version_id=UUID(str(enclosure["evidence_version_id"])),
                    source_ref=f"enclosure:{enclosure.get('key', '')}",
                    page_count=enclosure.get("page_count"),
                    page_from=enclosure.get("page_from"),
                    page_to=enclosure.get("page_to"),
                    tri=True,
                )
            )
    return tuple(out)


async def _client_of(ctx: AuthContext, found: Notice) -> UUID:
    client = (
        None
        if found.client_entity_id is None
        else await client_of_entity(ctx.tenant, found.client_entity_id)
    )
    if client is None:
        raise NotFound("client")
    return client


async def _draft_source(ctx: AuthContext, work_item_id: UUID) -> SourceDraft:
    """The letter, then the cited enclosures; the taxpayers sign (R-07)."""
    found = await notice(ctx, work_item_id)
    row = await _response_row(ctx.tenant, work_item_id)
    letter = (
        None
        if row["generated_document_id"] is None
        else await c11.latest_document_version(ctx.tenant, row["generated_document_id"])
    )
    if letter is None:
        raise LetterRendering
    documents = (
        SourceDocument(
            sha256=letter[1],
            generated_document_version_id=letter[0],
            source_ref=f"notice_response:{row['id']}",
            tri=True,
        ),
        *await _enclosures(row),
    )
    return SourceDraft(
        purpose=SOURCE,
        policy_family=SOURCE,
        client_id=await _client_of(ctx, found),
        title=f"Notice response · {found.notice_code or ''}".strip(" ·"),
        documents=documents,
        signers=tuple(
            SourceSigner(identity_method="email_code", contact_id=contact)
            for contact in row["signer_contact_ids"]
        ),
        engagement_id=found.engagement_id,
        work_item_id=work_item_id,
    )


# --- send for signature -----------------------------------------------------------------------


async def _with_confirmation_request(
    ctx: AuthContext, engagement_id: UUID, payment: dict[str, object] | None
) -> dict[str, object] | None:
    """US-7.1: a payment by the taxpayers gets one request for its confirmation. Accrued never
    takes a payment or holds an instrument (ADR P-27); the client uploads a confirmation."""
    if not payment or not payment.get("required") or payment.get(CONFIRMATION_ITEM):
        return payment
    item = await add_request_item(
        ctx,
        engagement_id,
        NewRequestItem(description=CONFIRMATION_REQUEST, audit_area="tax_payments"),
    )
    return {**payment, CONFIRMATION_ITEM: str(item.id)}


async def _final_letter(ctx: AuthContext, row: JsonRow) -> None:
    """What the taxpayers sign is the final letter (US-7.1), the sender's act under the partner's
    sign-off, which `send_for_signature` has just checked. A repeated call changes nothing."""
    document = cast(UUID, row["generated_document_id"])
    if await c11.document_is_final(ctx.tenant, document):
        return
    latest = await c11.latest_document_version(ctx.tenant, document)
    if latest is None:
        raise LetterRendering
    ref = c11.ApprovalRef(APPROVAL_KIND, cast(UUID, row["id"]), latest[1])
    token = _approving.set((ref, ctx.user_id))
    try:
        async with uow(ctx.tenant) as tx:
            await c11.render_final(tx, document, ref, c11.Requester("human", user_id=ctx.user_id))
    finally:
        _approving.reset(token)


async def send_for_signature(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """The partner's sign-off holds; the letter is rendered once; a C7 draft for SIG-02 d."""
    found = await notice(ctx, work_item_id)
    if not await signoff_ready(ctx.tenant, work_item_id):
        raise NotReady(facts={"blocking": "signoff"})
    row = await _response_row(ctx.tenant, work_item_id)
    if row["generated_document_id"] is None:
        async with uow(ctx.tenant) as tx:
            ticket = await c11.render(
                tx,
                c11.RenderRequest(
                    kind=SOURCE,
                    owner_ref=c11.OwnerRef(SOURCE, row["id"]),
                    scope=c11.RenderScope(
                        await _client_of(ctx, found), found.engagement_id, work_item_id
                    ),
                    template_version_id=row["template_version_id"],
                    requested_by=c11.Requester("human", user_id=ctx.user_id),
                ),
            )
            await tx.session.execute(
                text(
                    "UPDATE notice_responses SET generated_document_id = :g, "
                    "row_version = row_version + 1 WHERE id = :r"
                ),
                {"g": ticket.generated_document_id, "r": row["id"]},
            )
        row = await _response_row(ctx.tenant, work_item_id)
    if row["envelope_id"] is not None:
        return cast(UUID, row["envelope_id"])
    await _final_letter(ctx, row)
    envelope_id = await create_draft(ctx, SOURCE, work_item_id)
    payment = await _with_confirmation_request(
        ctx, found.engagement_id, cast("dict[str, object] | None", row["payment"])
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE notice_responses SET envelope_id = :e, payment = CAST(:p AS jsonb), "
                "row_version = row_version + 1 WHERE id = :r"
            ),
            {"e": envelope_id, "p": json.dumps(payment) if payment else None, "r": row["id"]},
        )
        tx.record(
            "notice_response.sent_for_signature",
            target=Target("notice", work_item_id),
            after=Ref(envelope=envelope_id),
        )
    return envelope_id


async def confirmation_item_of(ctx: AuthContext, work_item_id: UUID) -> UUID | None:
    """The payment's confirmation request, when there is one."""
    payment = cast(
        "dict[str, object]", (await _response_row(ctx.tenant, work_item_id))["payment"] or {}
    )
    found = payment.get(CONFIRMATION_ITEM)
    return UUID(str(found)) if found else None


# --- readiness --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Readiness:
    signed: bool
    payment_confirmed: bool
    enclosures_present: bool
    blocking: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blocking


def readiness_of(
    signed: bool, payment: Mapping[str, object] | None, enclosures: Sequence[Mapping[str, object]]
) -> Readiness:
    """Pure: both signatures, an accepted confirmation when a payment is due, each enclosure."""
    needs_payment = bool(payment and payment.get("required"))
    paid = not needs_payment or bool(payment and payment.get("confirmation_accepted"))
    present = all(
        e.get("evidence_version_id") or e.get("included") is False for e in enclosures
    )  # fmt: skip
    blocking = tuple(
        name
        for name, ok in (("envelope", signed), ("payment", paid), ("enclosures", present))
        if not ok
    )
    return Readiness(signed, paid, present, blocking)


async def readiness(ctx: AuthContext, work_item_id: UUID) -> Readiness:
    row = await _response_row(ctx.tenant, work_item_id)
    summary = await envelope_summary_for(ctx, SOURCE, work_item_id)
    return readiness_of(
        summary is not None and summary.status == "completed",
        cast("Mapping[str, object] | None", row["payment"]),
        cast("list[Mapping[str, object]]", row["enclosures"] or []),
    )


async def on_envelope_completed(event: OutboxEvent) -> None:
    """A `notice_response` envelope completed: publish ready-to-send when nothing else blocks."""
    if event.payload.get("source_kind") != SOURCE:
        return
    tenant = TenantContext(event.tenant_id, "system", "notices:envelope_completed")
    envelope_id = UUID(str(event.payload["envelope_id"]))
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT id, work_item_id, payment, enclosures FROM notice_responses "
                        "WHERE envelope_id = :e"
                    ),
                    {"e": envelope_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        return
    await _publish_when_ready(tenant, dict(row), signed=True)


async def _publish_when_ready(
    tenant: TenantContext,
    row: dict[str, Any],  # Any: JSON from the database
    *,
    signed: bool,
) -> None:
    """Ready to send, once: the signature's event or the confirmation's, whichever came last."""
    if not readiness_of(signed, row["payment"], row["enclosures"] or []).ready:
        return
    async with uow(tenant) as tx:
        tx.emit(
            NoticeResponseReadyToSend(
                work_item_id=row["work_item_id"],
                response_id=row["id"],
                assignee_user_id=await _assignee_of(tx.session, row["work_item_id"]),
            )
        )
        tx.record(
            "notice_response.ready_to_send",
            target=Target("notice", row["work_item_id"]),
            after=Ref(response=row["id"]),
        )


async def on_review_decision(event: OutboxEvent) -> None:
    """US-7.2: staff accepting (or undoing) the client's confirmation moves the payment band."""
    tenant = TenantContext(event.tenant_id, "system", "notices:payment_confirmation")
    items = await items_of_version(tenant, UUID(str(event.payload["evidence_version_id"])))
    if not items:
        return
    status = {str(i.id): i.status for i in items}
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, work_item_id, payment, enclosures, envelope_id "
                        "FROM notice_responses WHERE payment ->> :key = ANY(:ids)"
                    ),
                    {"key": CONFIRMATION_ITEM, "ids": list(status)},
                )
            )
            .mappings()
            .all()
        )
    for row in rows:
        accepted = status[row["payment"][CONFIRMATION_ITEM]] == "accepted"
        if bool(row["payment"].get("confirmation_accepted")) == accepted:
            continue
        # The day staff accepted the upload: the IRS's own date isn't read from the file.
        paid_on = (await today(tenant)).isoformat() if accepted else None
        payment = {**row["payment"], "confirmation_accepted": accepted, "paid_on": paid_on}
        async with uow(tenant) as tx:
            await tx.session.execute(
                text(
                    "UPDATE notice_responses SET payment = CAST(:p AS jsonb), "
                    "row_version = row_version + 1 WHERE id = :r"
                ),
                {"p": json.dumps(payment), "r": row["id"]},
            )
            tx.record(
                "notice_response.payment_confirmation_decided",
                target=Target("notice", row["work_item_id"]),
                after=Ref(accepted=int(accepted)),
            )
        if accepted and row["envelope_id"] is not None:
            await _publish_when_ready(
                tenant,
                {**row, "payment": payment},
                signed=await envelope_status(tenant, row["envelope_id"]) == "completed",
            )


SUBSCRIPTIONS: Final = {
    "envelope.completed": on_envelope_completed,
    "review_decision.recorded": on_review_decision,
    NoticeCreated.event_type: on_notice_created,
}


# --- mark sent --------------------------------------------------------------------------------


def follow_up_on(sent_on: date, days: int) -> date:
    return sent_on + timedelta(days=days)


async def mark_sent(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    channel: str,
    confirmation_no: str | None,
    sent_on: date,
    follow_up_days: int | None,
) -> tuple[date, date, str | None]:
    """A person records the send: sealed confirmation, then Sent to Awaiting IRS in one
    transaction."""
    found = await notice(ctx, work_item_id)
    ready = await readiness(ctx, work_item_id)
    if not ready.ready:
        raise NotReady(facts={"blocking": ",".join(ready.blocking)})
    row = await _response_row(ctx.tenant, work_item_id)
    days = follow_up_days if follow_up_days is not None else int(row["follow_up_days"])
    due = follow_up_on(sent_on, days)
    last4 = confirmation_no[-4:] if confirmation_no else None
    sealed = (
        await seal(ctx.tenant_id, confirmation_no.encode(), f"notice_sent_record:{work_item_id}")
        if confirmation_no
        else None
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO notice_sent_records (tenant_id, work_item_id, response_id, channel, "
                "confirmation_sealed, confirmation_last4, sent_on, follow_up_on, recorded_by, "
                "recorded_actor_kind) VALUES (:t, :w, :r, :c, :s, :l, :on, :due, :u, 'human')"
            ),
            {
                "t": ctx.tenant_id,
                "w": work_item_id,
                "r": row["id"],
                "c": channel,
                "s": sealed,
                "l": last4,
                "on": sent_on,
                "due": due,
                "u": ctx.user_id,
            },
        )
        await move(tx, found, "sent", actor_kind="human", actor_user_id=ctx.user_id)
        moved = replace(found, status="sent", row_version=found.row_version + 1)
        await move(tx, moved, "awaiting_irs", actor_kind="system", actor_user_id=None)
        tx.emit(
            NoticeResponseSent(
                work_item_id=work_item_id, sent_on=sent_on, follow_up_on=due,
            )
        )  # fmt: skip
        tx.record(
            "notice_response.sent",
            target=Target("notice", work_item_id),
            after=Ref(days_to_follow_up=(due - sent_on).days),
        )
    await signal_workflow(workflow_id(ctx.tenant_id, work_item_id), "sent", due.isoformat())
    return sent_on, due, last4


# --- agency replies ---------------------------------------------------------------------------


async def agency_reply(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    outcome: str,
    closed_on: date | None,
    note: str | None,
    evidence_version_id: UUID | None,
) -> None:
    """A person records the agency's reply: resolved closes the notice, escalated escalates it.
    The evidence is this notice's engagement's: the column has no key, so an id alone would reach
    across a wall."""
    found = await notice(ctx, work_item_id)
    if (
        evidence_version_id is not None
        and (await version_view(ctx.tenant, evidence_version_id)).engagement_id
        != found.engagement_id
    ):
        raise NotFound("evidence_version")
    sealed = (
        await seal(ctx.tenant_id, note.encode(), f"notice_agency_reply:{work_item_id}")
        if note
        else None
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO notice_agency_replies (tenant_id, work_item_id, outcome, closed_on, "
                "note_sealed, evidence_version_id, recorded_by, recorded_actor_kind) VALUES "
                "(:t, :w, :o, :c, :n, :e, :u, 'human')"
            ),
            {
                "t": ctx.tenant_id,
                "w": work_item_id,
                "o": outcome,
                "c": closed_on,
                "n": sealed,
                "e": evidence_version_id,
                "u": ctx.user_id,
            },
        )
        await move(
            tx,
            found,
            "closed" if outcome == "resolved" else "escalated",
            actor_kind="human",
            actor_user_id=ctx.user_id,
            closed_on=(closed_on or await today(ctx.tenant)) if outcome == "resolved" else None,
            escalated_reason=None if outcome == "resolved" else (note or "agency_reply"),
        )
        tx.record(
            "notice.agency_reply_recorded",
            target=Target("notice", work_item_id),
            after=Ref(resolved=int(outcome == "resolved")),
        )
    await signal_workflow(workflow_id(ctx.tenant_id, work_item_id), "agency_reply")


# --- the workflow's activities ----------------------------------------------------------------


async def _assignee_of(session: AsyncSession, work_item_id: UUID) -> UUID | None:
    """C16's recipient (N-04-T16, DEC-2311): whoever holds the notice when the event fires."""
    return (
        await session.execute(
            text("SELECT assignee_user_id FROM notices WHERE work_item_id = :w"),
            {"w": work_item_id},
        )
    ).scalar_one_or_none()


async def send_alert(given: AlertInput) -> None:
    tenant_id = UUID(given.tenant_id)
    work_item_id = UUID(given.work_item_id)
    async with uow(TenantContext(tenant_id, "system", "notices:alerts")) as tx:
        tx.emit(
            NoticeRespondBySoon(
                work_item_id=work_item_id,
                respond_by=date.fromisoformat(given.respond_by),
                days_left=given.days_left,
                assignee_user_id=await _assignee_of(tx.session, work_item_id),
            )
        )
        tx.record(
            "notice.respond_by_alerted",
            target=Target("notice", work_item_id),
            after=Ref(days_left=given.days_left),
        )


async def send_follow_up(given: FollowUpInput) -> None:
    tenant_id = UUID(given.tenant_id)
    work_item_id = UUID(given.work_item_id)
    async with uow(TenantContext(tenant_id, "system", "notices:alerts")) as tx:
        tx.emit(
            NoticeFollowUpDue(
                work_item_id=work_item_id,
                follow_up_on=date.fromisoformat(given.follow_up_on),
                assignee_user_id=await _assignee_of(tx.session, work_item_id),
            )
        )
        tx.record("notice.follow_up_alerted", target=Target("notice", work_item_id))
