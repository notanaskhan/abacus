"""Letter approval, send and amend (N-02-T33; N-02 §3.11, §4.2; ENG-04; C7; C11; C13; DEC-1468).

The composed letter (`letters.py`, N-02-T32) moves Draft → Partner approved → Sent → Signed, each
step a person's, on the current version of `engagement_letter_versions` (0560, 0563):

- **Request approval** (`letter.draft`, a person): stamps the draft with who asked and when, and
  tells each engagement partner (C16 `letter_approval_requested`). C13's `letter_partner_approval`
  gate waits on each partner while the request stands on a draft (`letter_partner_approvals_due`).
- **Approve** (`letter.approve`: engagement partner, fresh second factor, independence; the
  matrix and `authorise`): the draft's content hash is the approval. G1 must be decided, on or
  before the letter's date (409 `letter_before_acceptance`). The approval renders the approved
  draft final through C11 (the port in `letter_render.py`), with the approval C11 checks against
  the content hash (AC-15). Any later edit is a new draft version (`letters.draft_letter`): the
  approval stays on the superseded version, stale, and the letter is in Draft again.
- **Send** (`letter.send`, a person): a C7 draft from the `engagement_letter` source (the port in
  `letter_send.py`; the source's record is the approved version), signed by the client's signing
  officer, then countersigned by the approving partner (`letter_for_envelope`). The version keeps
  the envelope's id and takes no edit after it; a second Send answers the same envelope. C7's
  pre-send check refuses an envelope whose version is no longer the current approved letter
  (`letter_send_problems`). C7's own Send (SIG-02) sends it: `envelope.send_approved` moves
  the letter to Sent, and `envelope.completed` to Signed, locking the C11 document.
- **Amend** (`letter.amend`, the engagement partner): a signed letter takes an addendum, a new
  draft version of kind `addendum` amending it, rendered as its own C11 document (the signed one
  stays locked). It then follows the same path.

The database holds the person rule too (0563): only a transaction whose actor is the approving
person moves a version to `partner_approved`, and `letter.approved` is human-only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.acceptance_tables import g1_decision
from abacus.modules.engagements.contacts import designations_of
from abacus.modules.engagements.human_gates import DueGate, letter_gate_subject
from abacus.modules.engagements.letter_contract import ComposerLetterOut, LetterFeesIn
from abacus.modules.engagements.letter_render import (
    LetterFinalAsk,
    LetterRenderAsk,
    finalise_letter,
    lock_letter,
    render_letter,
)
from abacus.modules.engagements.letter_send import letter_envelope_status, send_letter_envelope
from abacus.modules.engagements.letters import (
    AMEND,
    APPROVE,
    DRAFT,
    SEND,
    LetterStale,
    composed_letter,
    compute_fees,
    fee_variables,
    letter_facts,
    letter_owner,
)
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.record import GateUnmet, LetterBeforeAcceptance
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    engagement_partners,
)

LETTER_PARTNER_APPROVAL: Final = "letter_partner_approval"
SOURCE_KIND: Final = "engagement_letter"  # signatures' `sources.LETTER`


class LetterNotApprovable(DomainConflict):
    """The letter is not a draft awaiting approval (or not a composed letter at all)."""

    code = "letter_not_approvable"


class LetterNotSendable(DomainConflict):
    """Only a partner-approved letter is sent (N-02 §3.11)."""

    code = "letter_not_sendable"


class LetterNotAmendable(DomainConflict):
    """Only a signed letter takes an addendum."""

    code = "letter_not_amendable"


class LetterSignerMissing(DomainConflict):
    """Send needs the client's signing officer designated (ENG-02) and an approving partner."""

    code = "letter_signer_missing"


# --- outbox events (identifiers only) -------------------------------------------------------


class LetterApprovalRequested(DomainEvent):
    """A person asked the engagement partners to approve the letter (C16, C13)."""

    event_type: ClassVar[str] = "letter.approval_requested"

    engagement_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class LetterApproved(DomainEvent):
    """The engagement partner approved the letter's content hash (C13 closes the gate)."""

    event_type: ClassVar[str] = "letter.approved"

    engagement_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


# --- the current version ------------------------------------------------------------------


_CURRENT = text(
    "SELECT v.* FROM engagement_letters l JOIN engagement_letter_versions v "
    "ON v.id = l.current_version_id WHERE l.engagement_id = :e AND l.mode = 'composed'"
)


async def _locked_current(tx: UnitOfWork, engagement_id: UUID) -> Mapping[str, object]:
    await tx.session.execute(
        text("SELECT 1 FROM engagement_letters WHERE engagement_id = :e FOR UPDATE"),
        {"e": engagement_id},
    )
    row = (await tx.session.execute(_CURRENT, {"e": engagement_id})).mappings().one_or_none()
    if row is None:
        raise NotFound("letter")
    return cast(Mapping[str, object], row)


def _person(ctx: AuthContext, action: str) -> None:
    """INV-1: requesting, approving, sending and amending are a person's own, in a live session."""
    if ctx.client:
        raise NotFound("letter")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _check_version(current: Mapping[str, object], if_match: str) -> None:
    at = cast(int, current["version_no"])
    if if_match.strip('"') != str(at):
        raise LetterStale(facts={"version": at})


def _letter_date(current: Mapping[str, object]) -> date:
    """The letter's date as drafted (`letter.date`, "July 12, 2027"), else the day the version
    was drafted (a template that does not print the date)."""
    words = cast(Mapping[str, object], current["variables"]).get("letter.date")
    if isinstance(words, str):
        try:
            return datetime.strptime(words, "%B %d, %Y").date()
        except ValueError:
            pass
    return cast(datetime, current["created_at"]).date()


# --- request approval -----------------------------------------------------------------------


async def request_approval(
    ctx: AuthContext, engagement_id: UUID, if_match: str
) -> ComposerLetterOut:
    """`POST …/letter/request-approval`: the draft waits on the engagement partners."""
    _person(ctx, DRAFT)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, DRAFT, ref.resource())
        current = await _locked_current(tx, engagement_id)
        _check_version(current, if_match)
        if current["status"] != "draft":
            raise LetterNotApprovable(facts={"status": str(current["status"])})
        partners = await engagement_partners(ctx.tenant_id, engagement_id)
        if not partners:
            raise LetterNotApprovable(facts={"reason": "no_engagement_partner"})
        if current["approval_requested_at"] is None:
            await tx.session.execute(
                text(
                    "UPDATE engagement_letter_versions SET approval_requested_at = :at, "
                    "approval_requested_by = :by WHERE id = :v"
                ),
                {"at": await clock.now(ctx.tenant), "by": ctx.user_id, "v": current["id"]},
            )
        tx.record(
            "letter.approval_requested",
            target=Target("engagement", engagement_id),
            after=Ref(version_no=cast(int, current["version_no"])),
        )
        tx.emit(
            LetterApprovalRequested(
                engagement_id=engagement_id,
                version_id=cast(UUID, current["id"]),
                recipient_user_ids=sorted(partners),
                by_user=ctx.user_id,
            )
        )
    return await _composed(ctx, engagement_id)


# --- approve --------------------------------------------------------------------------------


async def approve_letter(
    ctx: AuthContext, engagement_id: UUID, if_match: str
) -> ComposerLetterOut:
    """`POST …/letter/approve`: the engagement partner approves the draft's content hash."""
    _person(ctx, APPROVE)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, APPROVE, ref.resource())  # partner, fresh MFA, independence
        current = await _locked_current(tx, engagement_id)
        _check_version(current, if_match)
        if current["status"] != "draft":
            raise LetterNotApprovable(facts={"status": str(current["status"])})
        acceptance = await g1_decision(tx.session, engagement_id)
        if acceptance is None or not acceptance.accepted:
            raise GateUnmet(facts={"gate": "G1", "engagement_id": str(engagement_id)})
        if acceptance.decided_at.date() > _letter_date(current):
            # G1's date must come on or before the letter's date (N-02-T33).
            raise LetterBeforeAcceptance(facts={"engagement_id": str(engagement_id)})
        version_id = cast(UUID, current["id"])
        content_hash = str(current["content_hash"])
        final_id = await finalise_letter(
            tx,
            LetterFinalAsk(
                generated_document_id=cast(UUID, current["generated_document_id"]),
                version_id=version_id,
                content_hash=content_hash,
                approver_user_id=ctx.user_id,
            ),
        )
        await tx.session.execute(
            text(
                "UPDATE engagement_letter_versions SET status = 'partner_approved', "
                "approved_by = :by, approved_at = :at, approval_content_hash = :hash, "
                "final_document_version_id = :final WHERE id = :v"
            ),
            {
                "by": ctx.user_id,
                "at": await clock.now(ctx.tenant),
                "hash": content_hash,
                "final": final_id,
                "v": version_id,
            },
        )
        tx.record(
            "letter.approved",
            target=Target("engagement", engagement_id),
            after=Ref(
                version_no=cast(int, current["version_no"]),
                content_hash=content_hash,
                final_document_version_id=final_id,
            ),
        )
        tx.emit(
            LetterApproved(engagement_id=engagement_id, version_id=version_id, by_user=ctx.user_id)
        )
    return await _composed(ctx, engagement_id)


# --- send -----------------------------------------------------------------------------------


async def send_letter(ctx: AuthContext, engagement_id: UUID) -> UUID:
    """`POST …/letter/send`: the C7 draft SIG-02 opens. One envelope per approved version."""
    _person(ctx, SEND)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, SEND, ref.resource())
    async with tenant_session(ctx.tenant) as session:
        current = (await session.execute(_CURRENT, {"e": engagement_id})).mappings().one_or_none()
    if current is None:
        raise NotFound("letter")
    if current["status"] != "partner_approved":
        raise LetterNotSendable(facts={"status": str(current["status"])})
    if current["envelope_id"] is not None:
        return cast(UUID, current["envelope_id"])
    envelope_id = await send_letter_envelope(ctx, cast(UUID, current["id"]))
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        again = await _locked_current(tx, engagement_id)
        if again["id"] != current["id"] or again["status"] != "partner_approved":
            # The letter moved while the envelope was drafted: the draft stays for SIG-02 to
            # discard, and the letter keeps no envelope of a version it no longer is.
            raise LetterNotSendable(facts={"status": str(again["status"])})
        if again["envelope_id"] is not None:
            return cast(UUID, again["envelope_id"])
        await tx.session.execute(
            text("UPDATE engagement_letter_versions SET envelope_id = :env WHERE id = :v"),
            {"env": envelope_id, "v": again["id"]},
        )
        tx.record(
            "letter.envelope_drafted",
            target=Target("engagement", engagement_id),
            after=Ref(envelope_id=envelope_id, version_no=cast(int, again["version_no"])),
        )
    return envelope_id


# --- withdraw an envelope that ended unsigned (N-02-T35) -----------------------------------------

ENDED: Final = frozenset({"declined", "expired", "voided"})


class LetterNotWithdrawable(DomainConflict):
    """Only an approved or sent letter whose envelope was declined, expired or voided."""

    code = "letter_not_withdrawable"


async def withdraw_envelope(
    ctx: AuthContext, engagement_id: UUID, if_match: str
) -> ComposerLetterOut:
    """`POST …/letter/withdraw-envelope` (`letter.send`): the ended envelope is let go and the
    letter is back at its partner approval, so a fresh Send drafts a new envelope. The approval,
    its content hash and the final document stay as they were (0567's guard)."""
    _person(ctx, SEND)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, SEND, ref.resource())
        current = await _locked_current(tx, engagement_id)
        _check_version(current, if_match)
        envelope = cast(UUID | None, current["envelope_id"])
        if current["status"] not in ("partner_approved", "sent") or envelope is None:
            raise LetterNotWithdrawable(facts={"status": str(current["status"])})
        ended = await letter_envelope_status(ctx.tenant, envelope)
        if ended not in ENDED:
            raise LetterNotWithdrawable(facts={"envelope_status": str(ended)})
        await tx.session.execute(
            text(
                "UPDATE engagement_letter_versions SET status = 'partner_approved', "
                "envelope_id = NULL WHERE id = :v"
            ),
            {"v": current["id"]},
        )
        await tx.session.execute(
            text(
                "UPDATE engagement_letters SET envelope_id = NULL WHERE engagement_id = :e "
                "AND envelope_id = :env"
            ),
            {"e": engagement_id, "env": envelope},
        )
        tx.record(
            "letter.envelope_withdrawn",
            target=Target("engagement", engagement_id),
            after=Ref(envelope_id=envelope, version_no=cast(int, current["version_no"])),
        )
    return await _composed(ctx, engagement_id)


@dataclass(frozen=True)
class LetterEnvelope:
    """What the `engagement_letter` source prefills: the approved final, the client's signing
    officer (email code), then the approving partner's countersignature."""

    client_id: UUID
    engagement_id: UUID
    title: str
    generated_document_version_id: UUID
    content_hash: str
    client_signer_contact_id: UUID
    countersigner_user_id: UUID


_VERSION = text(
    "SELECT v.*, (l.current_version_id = v.id) AS is_current FROM engagement_letter_versions v "
    "JOIN engagement_letters l ON l.engagement_id = v.engagement_id WHERE v.id = :v"
)


async def _version(ctx: AuthContext, version_id: UUID) -> Mapping[str, object]:
    if ctx.client:
        raise NotFound("letter")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_VERSION, {"v": version_id})).mappings().one_or_none()
    if row is None:
        raise NotFound("letter")
    ref = await get_ref(ctx, cast(UUID, row["engagement_id"]))
    await authorise(ctx, SEND, ref.resource())
    return cast(Mapping[str, object], row)


async def letter_for_envelope(ctx: AuthContext, version_id: UUID) -> LetterEnvelope:
    """The approved letter version C7 drafts from (signatures' `engagement_letter` source)."""
    current = await _version(ctx, version_id)
    engagement_id = cast(UUID, current["engagement_id"])
    async with tenant_session(ctx.tenant) as session:
        engagement = await session.get(Engagement, engagement_id)
        designations = await designations_of(session, engagement_id)
    if engagement is None:
        raise NotFound("letter")
    if (
        not current["is_current"]
        or current["status"] != "partner_approved"
        or current["final_document_version_id"] is None
    ):
        raise LetterNotSendable(facts={"status": str(current["status"])})
    signer = next((d.contact_id for d in designations if d.designation == "signing_officer"), None)
    if signer is None:
        raise LetterSignerMissing(facts={"signer": "client"})
    kind = "Engagement letter" if current["kind"] == "original" else "Engagement letter addendum"
    return LetterEnvelope(
        client_id=engagement.client_id,
        engagement_id=engagement_id,
        title=f"{kind} · v{current['version_no']}",
        generated_document_version_id=cast(UUID, current["final_document_version_id"]),
        content_hash=str(current["approval_content_hash"]),
        client_signer_contact_id=signer,
        countersigner_user_id=cast(UUID, current["approved_by"]),
    )


async def letter_send_problems(ctx: AuthContext, version_id: UUID) -> list[str]:
    """C7's pre-send check: the envelope's version must still be the current approved letter."""
    current = await _version(ctx, version_id)
    if not current["is_current"] or current["status"] not in ("partner_approved", "sent"):
        return ["letter_changed"]
    return []


# --- amend ----------------------------------------------------------------------------------


async def amend_letter(ctx: AuthContext, engagement_id: UUID) -> ComposerLetterOut:
    """`POST …/letter/amend`: an addendum draft amending the signed letter."""
    _person(ctx, AMEND)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, AMEND, ref.resource())
        current = await _locked_current(tx, engagement_id)
        if current["status"] != "signed":
            raise LetterNotAmendable(facts={"status": str(current["status"])})
        engagement = await tx.session.get(Engagement, engagement_id)
        if engagement is None:
            raise NotFound("engagement")
        version_id = uuid4()
        amends = cast(UUID, current["id"])
        fee_terms = cast(Mapping[str, object], current["fee_terms"])
        overrides = {
            str(k): str(v)
            for k, v in cast(Mapping[str, object], fee_terms.get("overrides", {})).items()
        }
        sections = cast(Mapping[str, str], current["section_overrides"])
        # Today's facts (the addendum's own date), the person's overrides, the same fee terms.
        facts = await letter_facts(ctx, tx.session, engagement)
        values = {f.key: f.value for f in facts if f.value is not None}
        values.update(overrides)
        values.update(fee_variables(compute_fees(LetterFeesIn.model_validate(fee_terms["terms"]))))
        declared = set(cast(Mapping[str, object], current["variables"])) | set(overrides)
        ticket = await render_letter(
            tx,
            LetterRenderAsk(
                owner_id=letter_owner(engagement_id, amends),
                client_id=engagement.client_id,
                engagement_id=engagement_id,
                template_version_id=cast(UUID, current["template_version_id"]),
                requested_by=ctx.user_id,
                values=values,
                clause_states={
                    k: v != "off"
                    for k, v in cast(Mapping[str, str], current["clause_states"]).items()
                },
                overrides={
                    k: tuple(p.strip() for p in v.split("\n\n") if p.strip())
                    for k, v in sections.items()
                },
            ),
        )
        await tx.session.execute(
            text(
                "INSERT INTO engagement_letter_versions (id, tenant_id, engagement_id, "
                "version_no, kind, amends_version_id, template_version_id, clause_states, "
                "variables, section_overrides, fee_terms, generated_document_id, content_hash, "
                "status, created_by, created_by_kind) SELECT :id, tenant_id, engagement_id, "
                "version_no + 1, 'addendum', id, template_version_id, clause_states, "
                "CAST(:vars AS jsonb), section_overrides, fee_terms, :doc, :hash, 'draft', :by, "
                "'human' FROM engagement_letter_versions WHERE id = :amends"
            ),
            {
                "id": version_id,
                "vars": json.dumps(
                    {k: v for k, v in values.items() if k in declared},
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "doc": ticket.generated_document_id,
                "hash": ticket.content_hash,
                "by": ctx.user_id,
                "amends": amends,
            },
        )
        await tx.session.execute(
            text("UPDATE engagement_letters SET current_version_id = :v WHERE engagement_id = :e"),
            {"v": version_id, "e": engagement_id},
        )
        tx.record(
            "letter.amended",
            target=Target("engagement", engagement_id),
            after=Ref(
                version_no=cast(int, current["version_no"]) + 1,
                amends_version_id=amends,
                generated_document_id=ticket.generated_document_id,
                overrides=len(cast(Mapping[str, object], overrides)),
            ),
        )
    return await _composed(ctx, engagement_id)


# --- C7's events ----------------------------------------------------------------------------


_BY_ENVELOPE = text(
    "SELECT id, engagement_id, status, generated_document_id FROM engagement_letter_versions "
    "WHERE envelope_id = :env FOR UPDATE"
)


async def on_envelope_event(event: OutboxEvent) -> None:
    """C7 `envelope.send_approved` moves the letter to Sent; `envelope.completed` (a letter
    envelope) to Signed and locks its C11 document. Redelivery is a no-op."""
    raw = event.payload.get("envelope_id")
    if raw is None:
        return
    envelope_id = UUID(str(raw))
    completed = event.event_type == "envelope.completed"
    if completed and event.payload.get("source_kind") != SOURCE_KIND:
        return
    tenant = TenantContext(event.tenant_id, "system", "engagements:letter_envelope")
    async with tenant_session(tenant) as session:
        found = await _version_of(session, envelope_id)
    if found is None:
        return
    target = "signed" if completed else "sent"
    if found["status"] == target or (target == "sent" and found["status"] == "signed"):
        return
    async with uow(tenant) as tx:
        row = (await tx.session.execute(_BY_ENVELOPE, {"env": envelope_id})).mappings().one()
        status = str(row["status"])
        if status == target or status not in ("partner_approved", "sent"):
            # Superseded meanwhile, or already moved: nothing to record.
            tx.record(
                "letter.envelope_ignored",
                target=Target("engagement", cast(UUID, row["engagement_id"])),
                after=Ref(envelope_id=envelope_id, event=event.event_id),
            )
            return
        if target == "signed" and status == "partner_approved":
            # Completed before the send was seen (a record import): pass through Sent.
            await _move(tx, cast(UUID, row["id"]), "sent")
        await _move(tx, cast(UUID, row["id"]), target)
        engagement_id = cast(UUID, row["engagement_id"])
        await tx.session.execute(
            text("UPDATE engagement_letters SET envelope_id = :env WHERE engagement_id = :e"),
            {"env": envelope_id, "e": engagement_id},
        )
        if completed:
            await lock_letter(
                tx, cast(UUID, row["generated_document_id"]), f"envelope:{envelope_id}"
            )
        tx.record(
            f"letter.{target}",
            target=Target("engagement", engagement_id),
            after=Ref(envelope_id=envelope_id, event=event.event_id),
        )


async def _version_of(session: AsyncSession, envelope_id: UUID) -> Mapping[str, object] | None:
    row = (
        (
            await session.execute(
                text("SELECT status FROM engagement_letter_versions WHERE envelope_id = :env"),
                {"env": envelope_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    return cast(Mapping[str, object] | None, row)


async def _move(tx: UnitOfWork, version_id: UUID, status: str) -> None:
    await tx.session.execute(
        text("UPDATE engagement_letter_versions SET status = :s WHERE id = :v"),
        {"s": status, "v": version_id},
    )


# --- C13 ------------------------------------------------------------------------------------


async def letter_partner_approvals_due(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[DueGate]:
    """A requested draft waits on each engagement partner (one gate per partner, DEC-544)."""
    sql = (
        "SELECT v.id, v.engagement_id, e.client_id FROM engagement_letters l "
        "JOIN engagement_letter_versions v ON v.id = l.current_version_id "
        "JOIN engagements e ON e.id = v.engagement_id "
        "WHERE l.mode = 'composed' AND v.status = 'draft' AND v.approval_requested_at IS NOT NULL"
    )
    params: dict[str, object] = {}
    if engagement_id is not None:
        sql += " AND v.engagement_id = :e"
        params["e"] = engagement_id
    async with tenant_session(tenant) as session:
        rows = (await session.execute(text(sql), params)).all()
    out: list[DueGate] = []
    for r in rows:
        for partner in await engagement_partners(tenant.tenant_id, r.engagement_id):
            out.append(
                DueGate(
                    letter_gate_subject(r.id, partner),
                    r.engagement_id,
                    r.client_id,
                    partner,
                    "engagement_partner",
                )
            )
    return out


async def _composed(ctx: AuthContext, engagement_id: UUID) -> ComposerLetterOut:
    return await composed_letter(ctx, engagement_id)


SUBSCRIPTIONS: Final = {
    "envelope.send_approved": on_envelope_event,
    "envelope.completed": on_envelope_event,
}

__all__ = [
    "AMEND",
    "APPROVE",
    "LETTER_PARTNER_APPROVAL",
    "SEND",
    "SUBSCRIPTIONS",
    "LetterApprovalRequested",
    "LetterApproved",
    "LetterEnvelope",
    "LetterNotAmendable",
    "LetterNotApprovable",
    "LetterNotSendable",
    "LetterNotWithdrawable",
    "LetterSignerMissing",
    "amend_letter",
    "approve_letter",
    "letter_for_envelope",
    "letter_partner_approvals_due",
    "letter_send_problems",
    "on_envelope_event",
    "request_approval",
    "send_letter",
    "withdraw_envelope",
]
