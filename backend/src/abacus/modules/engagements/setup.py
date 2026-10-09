"""Acceptance, independence and the engagement letter, and the gate on client data (SPEC-025
AC-4 to AC-7; TASK-044).

Recorded, not performed (the firm's methodology and tools do the procedures): where each is
documented, and the engagement partner's decision and independence conclusion. The engagement
opens to client data when acceptance is `accepted` and the partner has concluded on
independence (and, if the firm requires it, the letter is recorded). Each member's own access
opening on their confirmation is TASK-045, in `authorise`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.events import IndependenceRequested
from abacus.modules.engagements.models import EngagementAcceptance, EngagementLetter
from abacus.modules.engagements.repository import (
    answer_confirmation,
    confirmations_of,
    confirmed_column,
    get_engagement,
    get_letter,
    insert_acceptance,
    is_confirmed,
    latest_acceptance,
    my_open_confirmations,
    other_engagements_of_client,
    put_letter,
    request_confirmation,
)
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.engagements.setup_steps import (
    Confirmation,
    Member,
    SetupFacts,
    Step,
    has_partner,
    steps,
    summary,
)
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    contacts,
    engagement_role_of,
    engagement_team,
    firm_admins,
    letter_policy,
    names_of,
)
from abacus.modules.organisations.api import client_names

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
    acceptance: EngagementAcceptance | None, letter: EngagementLetter | None, needs_letter: bool
) -> EngagementNotOpen | None:
    if acceptance is None:
        return AcceptanceMissing("acceptance")
    if acceptance.decision != "accepted":
        return AcceptanceDeclined("acceptance")
    if acceptance.independence_concluded_at is None:
        return IndependenceConclusionMissing("independence")
    if needs_letter and (
        letter is None or letter.status not in ("signed", "not_required_this_year")
    ):
        return LetterMissing("letter")
    return None


async def require_open(tenant: TenantContext, engagement_id: UUID) -> None:
    """Raise the reason the engagement isn't open to client data, or return (AC-7)."""
    async with tenant_session(tenant) as session:
        acceptance = await latest_acceptance(session, engagement_id)
        letter = await get_letter(session, engagement_id)
    blocked = _blocked(acceptance, letter, await letter_policy(tenant))
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
class OpenConfirmation:
    engagement_id: UUID
    engagement_name: str
    client_name: str
    status: str
    statement: str


async def my_confirmations(ctx: AuthContext) -> list[OpenConfirmation]:
    """The person's own requests still to answer (or declined), across the firm."""
    async with tenant_session(ctx.tenant) as session:
        rows = await my_open_confirmations(session, ctx.user_id)
        names = await client_names(session, [e.client_entity_id for _, e in rows])
    result: list[OpenConfirmation] = []
    for confirmation, engagement in rows:
        found = names.get(engagement.client_entity_id)
        client = found.client_name if found is not None else "the client"
        result.append(
            OpenConfirmation(
                engagement.id,
                engagement.name,
                client,
                confirmation.status,
                STATEMENT.format(client=client),
            )
        )
    return result


# --- Acceptance and the partner's conclusion (AC-4) -------------------------------------------


@dataclass(frozen=True)
class AcceptanceInput:
    decision: Literal["accepted", "declined"]
    documented_at: str
    kind: Literal["new_client", "continuance"] | None = None
    predecessor_auditor: str | None = None
    predecessor_communicated_on: date | None = None
    independence_concluded: bool = False
    independence_documented_at: str | None = None


def _clean(text: str | None, limit: int) -> str | None:
    kept = " ".join((text or "").split())[:limit]
    return kept or None


async def record_acceptance(ctx: AuthContext, engagement_id: UUID, given: AcceptanceInput) -> None:
    """The engagement partner's decision (fresh MFA), with where it's documented; a new record
    supersedes the old and keeps its file unless a new one is attached."""
    documented = _clean(given.documented_at, 300)
    if documented is None:
        raise DomainInvalid("where the decision is documented is required")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "acceptance.record", ref.resource())
        previous = await latest_acceptance(tx.session, engagement_id)
        kind = given.kind or (
            "continuance"
            if await other_engagements_of_client(tx.session, ref.client_id, engagement_id)
            else "new_client"
        )
        concluded_by = str(ctx.user_id) if given.independence_concluded else None
        new_client = kind == "new_client"
        await insert_acceptance(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            kind=kind,
            decision=given.decision,
            decided_by=str(ctx.user_id),
            documented_at=documented,
            # Carried forward from the previous record when not given again.
            predecessor_auditor=(
                _clean(given.predecessor_auditor, 200)
                or (previous.predecessor_auditor if previous is not None else None)
            )
            if new_client
            else None,
            predecessor_communicated_on=(
                given.predecessor_communicated_on
                or (previous.predecessor_communicated_on if previous is not None else None)
            )
            if new_client
            else None,
            independence_concluded_by=concluded_by,
            independence_concluded_at=datetime.now().astimezone() if concluded_by else None,
            independence_documented_at=_clean(given.independence_documented_at, 300)
            if concluded_by
            else None,
            **_file_columns(previous),
        )
        tx.record(
            "engagement.acceptance_recorded",
            target=Target("engagement", engagement_id),
            after=Ref(
                accepted=int(given.decision == "accepted"),
                independence_concluded=int(given.independence_concluded),
            ),
        )


def _file_columns(row: EngagementAcceptance | EngagementLetter | None) -> dict[str, object]:
    if row is None or row.file_key is None:
        return {}
    return {
        "file_key": row.file_key,
        "file_version_id": row.file_version_id,
        "file_fingerprint": row.file_fingerprint,
        "file_size": row.file_size,
        "file_media_type": row.file_media_type,
        "file_name": row.file_name,
    }


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


async def attach_acceptance_file(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, file: StoredFile
) -> None:
    """Inside evidence's unit of work, after the file is stored write-once (D2)."""
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, "acceptance.record", ref.resource())
    previous = await latest_acceptance(tx.session, engagement_id)
    if previous is None:
        raise NotFound("acceptance")
    values = {
        c: getattr(previous, c)
        for c in (
            "kind",
            "decision",
            "decided_by",
            "documented_at",
            "predecessor_auditor",
            "predecessor_communicated_on",
            "independence_concluded_by",
            "independence_concluded_at",
            "independence_documented_at",
        )
    }
    await insert_acceptance(
        tx.session,
        tenant_id=ctx.tenant_id,
        engagement_id=engagement_id,
        **values,
        **file.columns(),
    )
    tx.record(
        "engagement.acceptance_file_attached",
        target=Target("engagement", engagement_id),
        after=Ref(fingerprint=file.fingerprint),
    )


# --- The engagement letter (AC-6) -------------------------------------------------------------


@dataclass(frozen=True)
class LetterInput:
    status: LetterStatus
    letter_date: date | None = None
    reason: str | None = None
    link: str | None = None


async def record_letter(ctx: AuthContext, engagement_id: UUID, given: LetterInput) -> None:
    reason = _clean(given.reason, 500)
    if given.status == "not_required_this_year" and reason is None:
        raise DomainInvalid("a reason is needed when no letter is required this year")
    link = (given.link or "").strip() or None
    if link is not None and (not link.startswith("https://") or len(link) > 2000):
        raise DomainInvalid("the link must be an https address")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "letter.record", ref.resource())
        previous = await get_letter(tx.session, engagement_id)
        await put_letter(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "status": given.status,
                "letter_date": given.letter_date,
                "reason": reason,
                "link": link,
                "recorded_by": str(ctx.user_id),
                **_file_columns(previous),
            },
        )
        tx.record(
            "engagement.letter_recorded",
            target=Target("engagement", engagement_id),
            after=Ref(signed=int(given.status == "signed")),
        )


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
    ctx: AuthContext, engagement_id: UUID, which: Literal["acceptance", "letter"]
) -> StoredFile:
    """The file's reference, for evidence's verified download (`setup.read`)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "setup.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        row = (
            await latest_acceptance(session, engagement_id)
            if which == "acceptance"
            else await get_letter(session, engagement_id)
        )
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


@dataclass(frozen=True)
class ConfirmationView:
    user_id: UUID
    display_name: str
    status: str
    note: str | None
    before_act_1: bool
    answered_at: datetime | None


@dataclass(frozen=True)
class SetupView:
    acceptance: EngagementAcceptance | None
    letter: EngagementLetter | None
    confirmations: list[ConfirmationView]
    letter_required: bool
    blocked: str | None  # the gate's reason code, None when open
    steps: list[Step]  # SPEC-025 AC-10 (TASK-046)
    summary: str


async def setup(ctx: AuthContext, engagement_id: UUID) -> SetupView:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "setup.read", ref.resource())
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    sees_notes = role in _LEADS
    async with tenant_session(ctx.tenant) as session:
        engagement = await get_engagement(session, engagement_id)
        if engagement is None:
            raise NotFound("engagement")
        acceptance = await latest_acceptance(session, engagement_id)
        letter = await get_letter(session, engagement_id)
        rows = await confirmations_of(session, engagement_id)
        client = (await client_names(session, [engagement.client_entity_id])).get(
            engagement.client_entity_id
        )
        earlier = acceptance is None and bool(
            await other_engagements_of_client(session, engagement.client_id, engagement_id)
        )
    names = await names_of([r.user_id for r in rows])
    needs_letter = await letter_policy(ctx.tenant)
    blocked = _blocked(acceptance, letter, needs_letter)
    team = [Member(m.display_name, m.role) for m in await engagement_team(ctx, engagement_id)]
    admins: list[str] = []
    if not has_partner(team):
        admin_names = await names_of(await firm_admins(ctx.tenant_id))
        admins = sorted(admin_names.values())
    # Counts only (who the contacts are needs `client_contact.read`, on the People tab).
    reached = await contacts(ctx, engagement_id)
    facts = SetupFacts(
        engagement_name=engagement.name,
        client_name=client.client_name if client is not None else "",
        kind=acceptance.kind if acceptance else ("continuance" if earlier else "new_client"),
        period_start=engagement.fiscal_period_start,
        period_end=engagement.fiscal_period_end,
        team=team,
        firm_admins=admins,
        methodology_applied=engagement.methodology_version_id is not None,
        acceptance_decision=acceptance.decision if acceptance else None,
        acceptance_at=acceptance.created_at if acceptance else None,
        concluded=acceptance is not None and acceptance.independence_concluded_at is not None,
        letter_status=letter.status if letter else None,
        letter_required=needs_letter,
        confirmations=[Confirmation(names.get(r.user_id, ""), r.status) for r in rows],
        contacts_joined=sum(1 for c in reached if c.kind == "member"),
        contacts_invited=sum(1 for c in reached if c.kind == "invitation"),
        blocked=blocked.code if blocked is not None else None,
    )
    return SetupView(
        acceptance,
        letter,
        [
            ConfirmationView(
                r.user_id,
                names.get(r.user_id, ""),
                r.status,
                r.note if sees_notes or r.user_id == ctx.user_id else None,
                r.before_act_1,
                r.answered_at,
            )
            for r in rows
        ],
        needs_letter,
        blocked.code if blocked is not None else None,
        steps(facts),
        summary(facts),
    )


def confirmed_subquery(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID], user_id: UUID
) -> ColumnElement[bool]:
    """For identity's `visible()` (TASK-045 D2): the person confirmed for the row's engagement."""
    return confirmed_column(engagement_id, user_id)


async def confirmed_for(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> bool:
    """For identity's `authorise` (TASK-045 D2): the person confirmed for this engagement."""
    async with tenant_session(tenant) as session:
        return await is_confirmed(session, engagement_id, user_id)
