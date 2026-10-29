"""Acceptance, independence and the engagement letter, and the gate on client data (SPEC-025
AC-4 to AC-7; TASK-044).

Recorded, not performed (the firm's methodology and tools do the procedures): where each is
documented, and the engagement partner's decision and independence conclusion. The engagement
opens to client data when acceptance is `accepted` and the partner has concluded on
independence (and, if the firm requires it, the letter is recorded). Each member's own access
opening on their confirmation is TASK-045, in `authorise`. The routes that recorded acceptance,
the letter and a confirmation here retired with P-07-T59 (DEC-905); what stays is the gate, the
legacy rows' file attachments and the independence request and answer the v2 routes reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.acceptance_tables import G1Decision, g1_decision
from abacus.modules.engagements.contacts import attest_of
from abacus.modules.engagements.events import IndependenceRequested
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.independence_tables import g2_met
from abacus.modules.engagements.models import Engagement, EngagementLetter
from abacus.modules.engagements.repository import (
    answer_confirmation,
    client_column,
    confirmed_column,
    get_letter,
    is_confirmed,
    put_letter,
    request_confirmation,
)
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    letter_policy,
)
from abacus.modules.organisations.api import attest_client_ids

STATEMENT_VERSION: Final = "v1"
STATEMENT: Final = (
    "I confirm I am independent of {client} for this engagement, under the firm's "
    "independence policy."
)
LetterStatus = Literal["not_started", "sent", "signed", "not_required_this_year"]
_LEADS: Final = frozenset({"engagement_partner", "manager"})


# --- The gate (engagement-level AC-7) ---------------------------------------------------------


class EngagementNotOpen(DomainConflict):
    code = "engagement_not_open"


class AcceptanceMissing(EngagementNotOpen):
    code = "acceptance_missing"


class AcceptanceDeclined(EngagementNotOpen):
    code = "acceptance_declined"


class IndependenceConclusionMissing(EngagementNotOpen):
    code = "independence_conclusion_missing"


class LetterMissing(EngagementNotOpen):
    code = "letter_missing"


def _blocked(
    acceptance: G1Decision | None,
    letter: EngagementLetter | None,
    *,
    gates: frozenset[str],
    needs_letter: bool,
    g2: bool,
) -> EngagementNotOpen | None:
    """The first gate the engagement's type requires that is not met (F-03-T13: the per-type gate
    policy, so a tax or non-attest CAS engagement opens on G1 and G3 without G2). G1 is CLI-07's
    decision and G2 CLI-08's conclusion (P-07-T59, DEC-906)."""
    if "G1" in gates:
        if acceptance is None:
            return AcceptanceMissing("acceptance", facts={"gate": "G1"})
        if not acceptance.accepted:
            return AcceptanceDeclined("acceptance", facts={"gate": "G1"})
    if "G2" in gates and not g2:  # P-07-T41: callers pass `g2_met` (DEC-428)
        return IndependenceConclusionMissing("independence", facts={"gate": "G2"})
    if (
        "G3" in gates
        and needs_letter
        and (letter is None or letter.status not in ("signed", "not_required_this_year"))
    ):
        return LetterMissing("letter", facts={"gate": "G3"})
    return None


async def require_open(tenant: TenantContext, engagement_id: UUID) -> None:
    """Raise the reason the engagement isn't open to client data, or return (AC-7). Which gates
    apply comes from the engagement type's gate policy (chapter 03 §3.1.3)."""
    async with tenant_session(tenant) as session:
        engagement_type = (
            await session.execute(select(Engagement.type).where(Engagement.id == engagement_id))
        ).scalar_one_or_none()
        if engagement_type is None:
            raise NotFound("engagement")
        acceptance = await g1_decision(session, engagement_id)
        letter = await get_letter(session, engagement_id)
        g2 = await g2_met(session, engagement_id)
    gates = frozenset(required_gates(engagement_type))
    blocked = _blocked(
        acceptance, letter, gates=gates, needs_letter=await letter_policy(tenant), g2=g2
    )
    if blocked is not None:
        raise blocked


# --- Independence requests and confirmations (AC-5) -------------------------------------------


async def request_independence(tx: UnitOfWork, engagement_id: UUID, user_id: UUID) -> None:
    """Identity's member-added hook: the new member is asked to confirm (once)."""
    ref = await lock_ref(tx, engagement_id)
    if await request_confirmation(tx.session, ref.tenant_id, engagement_id, user_id):
        tx.record(
            "independence.requested",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=user_id),
        )
        tx.emit(IndependenceRequested(engagement_id=engagement_id, user_id=user_id))


async def answer_independence(
    ctx: AuthContext, engagement_id: UUID, *, confirm: bool, note: str | None
) -> None:
    """For oneself only: confirm the fixed statement, or decline with a note for the partner."""
    kept = (note or "").strip()[:1000] or None
    if not confirm and kept is None:
        raise DomainInvalid("a reason is needed to decline")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "independence.confirm", ref.resource())
        await request_confirmation(tx.session, ctx.tenant_id, engagement_id, ctx.user_id)
        await answer_confirmation(
            tx.session,
            engagement_id,
            ctx.user_id,
            status="confirmed" if confirm else "declined",
            statement_version=STATEMENT_VERSION if confirm else None,
            note=None if confirm else kept,
        )
        tx.record(
            "independence.confirmed" if confirm else "independence.declined",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=ctx.user_id),
        )


@dataclass(frozen=True)
class StoredFile:
    key: str
    version_id: str
    fingerprint: str
    size: int
    media_type: str
    name: str

    def columns(self) -> dict[str, object]:
        return {
            "file_key": self.key,
            "file_version_id": self.version_id,
            "file_fingerprint": self.fingerprint,
            "file_size": self.size,
            "file_media_type": self.media_type,
            "file_name": self.name,
        }


# --- The engagement letter (AC-6) -------------------------------------------------------------


async def attach_letter_file(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, file: StoredFile
) -> None:
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, "letter.record", ref.resource())
    previous = await get_letter(tx.session, engagement_id)
    await put_letter(
        tx.session,
        {
            "tenant_id": ctx.tenant_id,
            "engagement_id": engagement_id,
            "status": previous.status if previous is not None else "signed",
            "letter_date": previous.letter_date if previous is not None else None,
            "reason": previous.reason if previous is not None else None,
            "link": previous.link if previous is not None else None,
            "recorded_by": str(ctx.user_id),
            **file.columns(),
        },
    )
    tx.record(
        "engagement.letter_file_attached",
        target=Target("engagement", engagement_id),
        after=Ref(fingerprint=file.fingerprint),
    )


async def stored_file(
    ctx: AuthContext, engagement_id: UUID, which: Literal["letter"]
) -> StoredFile:
    """The file's reference, for evidence's verified download (`setup.read`). The acceptance
    file retired with SPEC-025's table (P-07-T59, DEC-906)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "setup.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        row = await get_letter(session, engagement_id)
    if row is None or row.file_key is None:
        raise NotFound("file")
    return StoredFile(
        row.file_key,
        str(row.file_version_id),
        str(row.file_fingerprint),
        int(row.file_size or 0),
        str(row.file_media_type),
        str(row.file_name),
    )


# --- The setup view (AC-4 to AC-7, and the setup page later) ----------------------------------


def confirmed_subquery(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID], user_id: UUID
) -> ColumnElement[bool]:
    """For identity's `visible()` (TASK-045 D2): the person confirmed for the row's engagement."""
    return confirmed_column(engagement_id, user_id)


async def confirmed_for(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> bool:
    """For identity's `authorise` (TASK-045 D2): the person confirmed for this engagement."""
    async with tenant_session(tenant) as session:
        return await is_confirmed(session, engagement_id, user_id)


# --- P-07-T24: G2 v2's one answer (ADR-164 item 4) ----------------------------------------------


async def independence_cleared(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> bool:
    """Whether the person is cleared on this engagement: their own confirmation for it, which no
    later decline supersedes (one row per person and engagement). Unknown answers False (fail
    closed). The one answer for P-04's sign-off, assignment and `authorise` (ADR-164 item 4);
    the annual firm-wide confirmation joins it when G-01 delivers it (DEC-91)."""
    return await confirmed_for(tenant, engagement_id, user_id)


async def g2_blocks(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> bool:
    """Whether G2 keeps this person from being assigned or signing off here: the engagement's
    client is an attest client (unknown counts as attest) and the person is not cleared
    (ADR-164 item 2). A non-attest client's engagement is never gated."""
    if await independence_cleared(tenant, engagement_id, user_id):
        return False
    return await attest_of(tenant, engagement_id) is not False


def attest_column(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID],
) -> ColumnElement[bool]:
    """For identity's `visible()` under `g2_blocks_view`: the row's engagement's client is an
    attest client (P-07-T24, ADR-164 item 3)."""
    return client_column(engagement_id).in_(attest_client_ids().scalar_subquery())
