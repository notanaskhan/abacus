"""Independence, live (P-07-T41; CLI-08; SPEC-332 AC-17 to AC-22, AC-27, AC-28; DEC-428).

- **Confirmation** is each team member's own: the three statements of the engagement's statement
  version ticked (the statement words are data, the screen's), an optional interests note, or a
  decline with a note. Notes are sealed per tenant, bound to the person's row; a decline's note is
  read only by the engagement partner and the person.
- **The summary** (CLI-08 a): every member bound by independence, "{confirmed} of {total}", the
  banner's blockers as codes and identifiers, the conclusion, the SKE designee, and each member's
  annual confirmation read from G-01 for a reader who may read it (`independence.annual_read`).
- **NAS** (attest clients only): every service the firm provides the client outside the attest
  family is a row on the attest engagement; partners and managers prepare it, only the engagement
  partner concludes it, and neither happens without an SKE designee (DEC-63). Rows and events are
  insert-only; the newest event is the row's state.
- **The conclusion** is the engagement partner's, a partner-level member, with fresh MFA, once
  every member confirmed, every conflict hit on the client is cleared and, on an attest client,
  the SKE designee is named and every NAS row decided (409 `independence_preconditions_unmet`
  with one count per reason code). Insert-only; a later one supersedes the newest. G2 is met on
  Independent or Independent with safeguards while no breach is open (`independence_tables`).
- **Breaches** are logged and closed by three insert-only events (evaluated, TCWG communicated,
  remediated), each once.
- **Rotation** (AC-27): years served count the engagements, back along the `prior_engagement_id`
  chain from this one, on whose team the person sat without a gap.

Every write: a live person (never an agent, the platform, a client or a support session), the
matrix action on the engagement, one unit of work, one audit event. `conclude_independence` is
named only here, in its route and in `engagements/api.py` (banned pattern INDEP-001).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.clock import now
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.contacts import attest_of, designations_of
from abacus.modules.engagements.events import IndependenceConclusionDue
from abacus.modules.engagements.gate_policy import FAMILY
from abacus.modules.engagements.independence_tables import (
    BREACH_STEPS,
    POSITIVE,
    breach_events,
    breaches,
    conclusions,
    latest_conclusion,
    nas_events,
    nas_rows,
    open_breach_ids,
)
from abacus.modules.engagements.models import Engagement, IndependenceConfirmation
from abacus.modules.engagements.record import GateMet
from abacus.modules.engagements.repository import request_confirmation
from abacus.modules.engagements.service import EngagementRef, get_ref, lock_ref
from abacus.modules.engagements.transitions import IllegalTransition
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    engagement_team,
    engagement_team_query,
    has_current_annual_confirmation,
    hidden_clients,
    member_facts,
)
from abacus.modules.organisations.api import standing_conflict_results

READ: Final = "independence.read"
CONFIRM: Final = "independence.confirm"
REMIND: Final = "independence.remind"
NAS: Final = "nas.evaluate"
BREACH: Final = "independence.breach_manage"
CONCLUDE: Final = "independence.conclude"
ACTIONS: Final = (READ, CONFIRM, REMIND, NAS, BREACH, CONCLUDE)
ANNUAL_READ: Final = "independence.annual_read"
# The engagement roles asked to confirm on joining (the `independence.confirm` matrix row).
BOUND_ROLES: Final = frozenset(
    {"engagement_partner", "manager", "senior", "staff", "reviewer", "eqr_reviewer", "specialist"}
)
STATEMENT_COUNT: Final = 3  # CLI-08 e: three statements
# The platform default until firm settings hold integers (`rotation_review_years`, seed 7).
ROTATION_REVIEW_YEARS: Final = 7
# The statuses in which an engagement is a service the firm provides (DEC-128's list).
_PROVIDED: Final = ("accepted", "contracted", "active", "on_hold", "delivered")
_CHAIN_LIMIT: Final = 60

ConfirmationAnswer = Literal["requested", "confirmed", "declined"]
Option = Literal["independent", "independent_with_safeguards", "not_independent"]
NasStatus = Literal["pending", "concluded", "not_applicable"]
BreachKind = Literal["evaluated", "tcwg_communicated", "remediated"]
Reason = Literal[
    "member_not_confirmed",
    "member_declined",
    "conflict_not_cleared",
    "ske_designee_missing",
    "nas_not_evaluated",
    "breach_open",
]


# --- errors (`error-codes.yaml`) ----------------------------------------------------------------


class IndependencePreconditionsUnmet(DomainConflict):
    """The conclusion (or a NAS evaluation) waits on the blockers counted in `facts`."""

    code = "independence_preconditions_unmet"


class NasDecided(DomainConflict):
    """The engagement partner decided this NAS row; only they record another evaluation."""

    code = "decision_locked"


class ConclusionSuperseded(DomainConflict):
    """Another conclusion superseded the one this conclusion read as newest first (ED-117,
    DEC-461): read the engagement again and conclude on the newest."""

    code = "stale_version"


# The one-successor chain (0175): one first conclusion per engagement, one successor each.
_ONE_SUCCESSOR: Final = frozenset(
    {"independence_conclusions_first", "independence_conclusions_tenant_id_supersedes_id_key"}
)


def _constraint(exc: DBAPIError) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "constraint_name", None) or getattr(
        getattr(orig, "__cause__", None), "constraint_name", None
    )


# --- outbox events (identifiers and codes only) ------------------------------------------------


class IndependenceConfirmed(DomainEvent):
    event_type: ClassVar[str] = "independence.confirmed"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class IndependenceDeclined(DomainEvent):
    """For the engagement partner's notification (its kind registers with P-07-T47)."""

    event_type: ClassVar[str] = "independence.declined"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class IndependenceConcluded(DomainEvent):
    event_type: ClassVar[str] = "independence.concluded"

    engagement_id: Annotated[UUID, classified("internal")]
    conclusion_id: Annotated[UUID, classified("internal")]
    option: Annotated[str, classified("internal")]


# --- views --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Blocker:
    reason_code: Reason
    ref_type: str
    ref_id: UUID


@dataclass(frozen=True)
class MemberConfirmation:
    user_id: UUID
    display_name: str
    role: str
    confirmation: ConfirmationAnswer
    answered_at: datetime | None = None
    statement_version: str | None = None
    decline_note: str | None = None
    reminder_count: int = 0
    annual_confirmed: bool | None = None


@dataclass(frozen=True)
class ConclusionView:
    id: UUID
    option: str
    safeguards: str | None
    concluded_by: UUID
    concluded_at: datetime
    supersedes_id: UUID | None


@dataclass(frozen=True)
class SummaryView:
    engagement_id: UUID
    attest_client: bool
    confirmed: int
    total: int
    members: list[MemberConfirmation]
    blockers: list[Blocker]
    conclusion: ConclusionView | None
    ske_designee_contact_id: UUID | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class ConfirmationView:
    engagement_id: UUID
    user_id: UUID
    confirmation: ConfirmationAnswer
    answered_at: datetime | None


@dataclass(frozen=True)
class RotationRow:
    user_id: UUID
    display_name: str
    role: str
    years_served: int
    familiarity_flag: bool


@dataclass(frozen=True)
class RotationView:
    review_years: int
    rows: list[RotationRow]


@dataclass(frozen=True)
class NasRow:
    service_code: str
    provided: bool
    status: NasStatus
    evaluation: str | None = None
    safeguards: str | None = None
    ske_contact_id: UUID | None = None
    evaluated_by: UUID | None = None
    evaluated_at: datetime | None = None


@dataclass(frozen=True)
class NasView:
    attest_client: bool
    ske_designee_contact_id: UUID | None
    rows: list[NasRow]


@dataclass(frozen=True)
class BreachEvent:
    kind: str
    note: str | None
    recorded_by: UUID
    recorded_at: datetime


@dataclass(frozen=True)
class BreachView:
    id: UUID
    engagement_id: UUID
    description: str
    user_id: UUID | None
    events: list[BreachEvent]
    resolved: bool


# --- sealing and guards -------------------------------------------------------------------------


def _binding(kind: str, *parts: object) -> str:
    """What a sealed value is bound to: its own row and field, so it opens only there."""
    return hashlib.sha256(":".join([kind, *(str(p) for p in parts)]).encode()).hexdigest()


async def _seal(tenant: TenantContext, text: str, kind: str, *parts: object) -> bytes:
    return await seal(tenant.tenant_id, text.encode(), _binding(kind, *parts))


async def _open(
    tenant: TenantContext, sealed: bytes | None, kind: str, *parts: object
) -> str | None:
    if sealed is None:
        return None
    return (await open_sealed(tenant.tenant_id, sealed, _binding(kind, *parts))).decode()


def _live_human(ctx: AuthContext, action: str) -> None:
    """INV-1 (`require_live_human`): a person's own act, never an agent, the platform, a client
    principal or a break-glass support session."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _readable(ctx: AuthContext, engagement_id: UUID) -> EngagementRef:
    _live_human(ctx, READ)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, READ, ref.resource())
    return ref


async def _writable(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, action: str
) -> EngagementRef:
    _live_human(ctx, action)
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, action, ref.resource())
    return ref


# --- the facts every view and the conclusion share ----------------------------------------------


# A NAS service: its code, its row (None before the first evaluation), the engagement it comes
# from (or this one) and its newest event.
_NasFact = tuple[str, UUID | None, UUID, dict[str, object] | None]


@dataclass
class _Facts:
    attest: bool
    members: list[tuple[UUID, str, str]]  # user, name, role
    confirmations: dict[UUID, IndependenceConfirmation]
    ske_contact_ids: list[UUID]
    nas: list[_NasFact] = field(default_factory=list[_NasFact])
    conflicts: list[tuple[UUID, UUID]] = field(default_factory=list[tuple[UUID, UUID]])
    breaches: list[UUID] = field(default_factory=list[UUID])


async def _services(session: AsyncSession, ref: EngagementRef) -> dict[str, UUID]:
    """The client's other engagements outside the attest family that the firm provides: one NAS
    service code (the engagement type) each, with the first such engagement's id (AC-21)."""
    rows = await session.execute(
        select(Engagement.type, Engagement.id)
        .where(
            Engagement.client_id == ref.client_id,
            Engagement.id != ref.id,
            Engagement.status.in_(_PROVIDED),
        )
        .order_by(Engagement.type, Engagement.id)
    )
    found: dict[str, UUID] = {}
    for engagement_type, engagement_id in rows.all():
        if FAMILY.get(str(engagement_type)) != "attest":
            found.setdefault(str(engagement_type), engagement_id)
    return found


async def _nas_state(
    session: AsyncSession, engagement_id: UUID
) -> dict[str, tuple[UUID, dict[str, object] | None]]:
    """Each NAS row of the engagement: its id and its newest event (or None)."""
    rows = (
        await session.execute(
            select(nas_rows.c.id, nas_rows.c.service_code).where(
                nas_rows.c.engagement_id == engagement_id
            )
        )
    ).all()
    out: dict[str, tuple[UUID, dict[str, object] | None]] = {}
    for row_id, code in rows:
        latest = (
            (
                await session.execute(
                    select(nas_events)
                    .where(nas_events.c.nas_id == row_id)
                    .order_by(nas_events.c.seq.desc())
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        out[str(code)] = (cast(UUID, row_id), dict(latest) if latest is not None else None)
    return out


async def _facts(ctx: AuthContext, session: AsyncSession, ref: EngagementRef) -> _Facts:
    engagement_id = ref.id
    attest = await attest_of(ctx.tenant, engagement_id) is not False
    team = [
        (m.user_id, m.display_name, str(m.role))
        for m in await engagement_team(ctx, engagement_id)
        if m.role in BOUND_ROLES
    ]
    rows = (
        (
            await session.execute(
                select(IndependenceConfirmation).where(
                    IndependenceConfirmation.engagement_id == engagement_id
                )
            )
        )
        .scalars()
        .all()
    )
    ske = [
        d.contact_id
        for d in await designations_of(session, engagement_id)
        if d.designation == "ske_designee"
    ]
    facts = _Facts(attest, team, {r.user_id: r for r in rows}, ske)
    if attest:
        services = await _services(session, ref)
        state = await _nas_state(session, engagement_id)
        for code in sorted(set(services) | set(state)):
            row_id, latest = state.get(code, (None, None))
            facts.nas.append((code, row_id, services.get(code, engagement_id), latest))
    facts.conflicts = await standing_conflict_results(ctx.tenant, ref.client_id)
    facts.breaches = await open_breach_ids(session, engagement_id)
    return facts


def _blockers(
    facts: _Facts, engagement_id: UUID, *, with_breaches: bool, hidden: frozenset[UUID]
) -> list[Blocker]:
    """The banner's reasons. Conflict results on clients the reader is walled from collapse into
    one `conflict_not_cleared` naming the engagement: no result id, no count (DEC-429, L4;
    DEC-43, DEC-375)."""
    out: list[Blocker] = []
    for user_id, _, _ in facts.members:
        row = facts.confirmations.get(user_id)
        status = row.status if row is not None else "requested"
        if status == "declined":
            out.append(Blocker("member_declined", "user", user_id))
        elif status != "confirmed":
            out.append(Blocker("member_not_confirmed", "user", user_id))
    out.extend(
        Blocker("conflict_not_cleared", "conflict_result", result)
        for result, client in facts.conflicts
        if client not in hidden
    )
    if any(client in hidden for _, client in facts.conflicts):
        out.append(Blocker("conflict_not_cleared", "engagement", engagement_id))
    if facts.attest:
        if not facts.ske_contact_ids:
            out.append(Blocker("ske_designee_missing", "engagement", engagement_id))
        for _, row_id, source, latest in facts.nas:
            if latest is None or latest["status"] == "pending":
                if row_id is not None:
                    out.append(Blocker("nas_not_evaluated", "nas_evaluation", row_id))
                else:
                    out.append(Blocker("nas_not_evaluated", "engagement", source))
    if with_breaches:
        out.extend(Blocker("breach_open", "independence_breach", b) for b in facts.breaches)
    return out


async def _hidden(ctx: AuthContext, facts: _Facts) -> frozenset[UUID]:
    """The matched clients of standing conflict results the reader is walled from."""
    clients = {client for _, client in facts.conflicts}
    if not clients:
        return frozenset()
    return await hidden_clients(ctx.tenant, ctx.user_id, clients)


def _counts(blockers: Sequence[Blocker]) -> dict[str, object]:
    counts: dict[str, object] = {}
    for b in blockers:
        counts[b.reason_code] = cast(int, counts.get(b.reason_code, 0)) + 1
    return counts


async def _conclusion_view(
    tenant: TenantContext, session: AsyncSession, engagement_id: UUID
) -> ConclusionView | None:
    latest = await latest_conclusion(session, engagement_id)
    if latest is None:
        return None
    return ConclusionView(
        latest.id,
        latest.option,
        await _open(tenant, latest.safeguards_sealed, "independence_conclusion", latest.id),
        latest.concluded_by,
        latest.concluded_at,
        latest.supersedes_id,
    )


# --- reads --------------------------------------------------------------------------------------


async def independence_summary(ctx: AuthContext, engagement_id: UUID) -> SummaryView:
    """CLI-08 a: the members, the count, the banner's blockers and the conclusion."""
    ref = await _readable(ctx, engagement_id)
    reads_annual = ANNUAL_READ in await allowed_actions(
        ctx, Resource.firm(ctx.tenant_id), (ANNUAL_READ,)
    )
    allowed = await allowed_actions(ctx, ref.resource(), ACTIONS)
    # A decline's note is the engagement partner's to read (the conclusion's holder) and the
    # person's own.
    concluder = CONCLUDE in allowed
    async with tenant_session(ctx.tenant) as session:
        facts = await _facts(ctx, session, ref)
        conclusion = await _conclusion_view(ctx.tenant, session, engagement_id)
    members: list[MemberConfirmation] = []
    for user_id, name, role in facts.members:
        row = facts.confirmations.get(user_id)
        status = cast(ConfirmationAnswer, row.status if row is not None else "requested")
        sees_note = concluder or user_id == ctx.user_id
        note = None
        if row is not None and status == "declined" and sees_note:
            note = await _open(
                ctx.tenant,
                row.decline_note,
                "independence_confirmation.decline_note",
                engagement_id,
                user_id,
            )
        annual = (
            await has_current_annual_confirmation(ctx.tenant, user_id) if reads_annual else None
        )
        members.append(
            MemberConfirmation(
                user_id,
                name,
                role,
                status,
                row.answered_at if row is not None else None,
                row.statement_version if row is not None else None,
                note,
                row.reminder_count if row is not None else 0,
                annual,
            )
        )
    return SummaryView(
        engagement_id,
        facts.attest,
        sum(1 for m in members if m.confirmation == "confirmed"),
        len(members),
        members,
        _blockers(facts, engagement_id, with_breaches=True, hidden=await _hidden(ctx, facts)),
        conclusion,
        facts.ske_contact_ids[0] if facts.ske_contact_ids else None,
        sorted(a for a in ACTIONS if a in allowed),
    )


async def rotation(ctx: AuthContext, engagement_id: UUID) -> RotationView:
    """AC-27: years served back along the prior-engagement chain, without a gap, never typed."""
    ref = await _readable(ctx, engagement_id)
    team = [m for m in await engagement_team(ctx, engagement_id) if m.role in BOUND_ROLES]
    roster = engagement_team_query().subquery("roster")
    chain_teams: list[set[UUID]] = []
    async with tenant_session(ctx.tenant) as session:
        current: UUID | None = ref.id
        seen: set[UUID] = set()
        while current is not None and current not in seen and len(seen) < _CHAIN_LIMIT:
            seen.add(current)
            members = await session.execute(
                select(roster.c.user_id).where(roster.c.engagement_id == current)
            )
            chain_teams.append({cast(UUID, u) for u in members.scalars().all()})
            current = (
                await session.execute(
                    select(Engagement.prior_engagement_id).where(Engagement.id == current)
                )
            ).scalar_one_or_none()
    rows: list[RotationRow] = []
    for m in team:
        years = 0
        for on_team in chain_teams:
            if m.user_id not in on_team:
                break
            years += 1
        rows.append(
            RotationRow(
                m.user_id,
                m.display_name,
                str(m.role),
                years,
                years >= ROTATION_REVIEW_YEARS,
            )
        )
    return RotationView(ROTATION_REVIEW_YEARS, rows)


async def nas(ctx: AuthContext, engagement_id: UUID) -> NasView:
    """CLI-08 b (AC-21, AC-22); a non-attest client answers no rows."""
    ref = await _readable(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        facts = await _facts(ctx, session, ref)
        rows = [await _nas_row(ctx.tenant, code, latest) for code, _, _, latest in facts.nas]
    return NasView(
        facts.attest,
        facts.ske_contact_ids[0] if facts.ske_contact_ids else None,
        rows if facts.attest else [],
    )


async def _nas_row(tenant: TenantContext, code: str, latest: dict[str, object] | None) -> NasRow:
    if latest is None:
        return NasRow(code, True, "pending")
    event_id = cast(UUID, latest["id"])
    return NasRow(
        code,
        bool(latest["provided"]),
        cast(NasStatus, latest["status"]),
        await _open(
            tenant, cast(bytes | None, latest["evaluation_sealed"]), "nas.evaluation", event_id
        ),
        await _open(
            tenant, cast(bytes | None, latest["safeguards_sealed"]), "nas.safeguards", event_id
        ),
        cast(UUID | None, latest["ske_contact_id"]),
        cast(UUID, latest["recorded_by"]),
        cast(datetime, latest["recorded_at"]),
    )


# --- confirmation (AC-17) -----------------------------------------------------------------------


async def confirm_independence(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    statement_version: str,
    statement_codes: Sequence[str],
    interests_note: str | None,
) -> ConfirmationView:
    """The caller's own confirmation: the three statements of `statement_version` ticked."""
    _live_human(ctx, CONFIRM)
    codes = list(dict.fromkeys(statement_codes))
    if len(codes) != STATEMENT_COUNT:
        raise DomainInvalid(facts={"field": "statement_codes"})
    kept = (interests_note or "").strip() or None
    async with uow(ctx.tenant) as tx:
        await _writable(tx, ctx, engagement_id, CONFIRM)
        await request_confirmation(tx.session, ctx.tenant_id, engagement_id, ctx.user_id)
        answered = await now(ctx.tenant)
        await tx.session.execute(
            update(IndependenceConfirmation)
            .where(
                IndependenceConfirmation.engagement_id == engagement_id,
                IndependenceConfirmation.user_id == ctx.user_id,
            )
            .values(
                status="confirmed",
                statement_version=statement_version,
                statements={"version": statement_version, "codes": codes},
                interests_note=(
                    await _seal(
                        ctx.tenant,
                        kept,
                        "independence_confirmation.interests_note",
                        engagement_id,
                        ctx.user_id,
                    )
                    if kept
                    else None
                ),
                decline_note=None,
                note=None,
                answered_at=answered,
            )
        )
        tx.record(
            "independence.confirmed",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=ctx.user_id),
        )
        tx.emit(IndependenceConfirmed(engagement_id=engagement_id, user_id=ctx.user_id))
        # P-07-T47: the last confirmation makes the conclusion the engagement partner's.
        if await _conclusion_due(tx.session, engagement_id):
            tx.emit(IndependenceConclusionDue(engagement_id=engagement_id))
    return ConfirmationView(engagement_id, ctx.user_id, "confirmed", answered)


async def _conclusion_due(session: AsyncSession, engagement_id: UUID) -> bool:
    """Every member confirmed (none requested or declined) and no conclusion yet."""
    still_open = await session.scalar(
        select(func.count())
        .select_from(IndependenceConfirmation)
        .where(
            IndependenceConfirmation.engagement_id == engagement_id,
            or_(
                IndependenceConfirmation.status.in_(("requested", "declined")),
                IndependenceConfirmation.statements.is_(None),
            ),
        )
    )
    concluded = await session.scalar(
        select(func.count())
        .select_from(conclusions)
        .where(conclusions.c.engagement_id == engagement_id)
    )
    return not still_open and not concluded


async def decline_independence(
    ctx: AuthContext, engagement_id: UUID, *, note: str
) -> ConfirmationView:
    """The caller's own decline: the note sealed, the member stays not cleared (DF-06)."""
    _live_human(ctx, CONFIRM)
    kept = note.strip()
    if not kept:
        raise DomainInvalid(facts={"field": "note"})
    async with uow(ctx.tenant) as tx:
        await _writable(tx, ctx, engagement_id, CONFIRM)
        await request_confirmation(tx.session, ctx.tenant_id, engagement_id, ctx.user_id)
        answered = await now(ctx.tenant)
        await tx.session.execute(
            update(IndependenceConfirmation)
            .where(
                IndependenceConfirmation.engagement_id == engagement_id,
                IndependenceConfirmation.user_id == ctx.user_id,
            )
            .values(
                status="declined",
                statement_version=None,
                statements=None,
                interests_note=None,
                decline_note=await _seal(
                    ctx.tenant,
                    kept,
                    "independence_confirmation.decline_note",
                    engagement_id,
                    ctx.user_id,
                ),
                note=None,
                answered_at=answered,
            )
        )
        tx.record(
            "independence.declined",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=ctx.user_id),
        )
        tx.emit(IndependenceDeclined(engagement_id=engagement_id, user_id=ctx.user_id))
    return ConfirmationView(engagement_id, ctx.user_id, "declined", answered)


# --- NAS (AC-21, AC-22) -------------------------------------------------------------------------


async def evaluate_nas(
    ctx: AuthContext,
    engagement_id: UUID,
    service_code: str,
    *,
    provided: bool,
    status: NasStatus,
    evaluation: str | None,
    safeguards: str | None,
    ske_contact_id: UUID | None,
) -> NasRow:
    """A partner or manager prepares a NAS row; only the engagement partner concludes it (or
    marks it not applicable). Refused without an SKE designee; insert-only events."""
    _live_human(ctx, NAS)
    async with uow(ctx.tenant) as tx:
        ref = await _writable(tx, ctx, engagement_id, NAS)
        if await attest_of(ctx.tenant, engagement_id) is False:
            raise DomainInvalid(facts={"field": "attest_client"})
        ske = [
            d.contact_id
            for d in await designations_of(tx.session, engagement_id)
            if d.designation == "ske_designee"
        ]
        if not ske:
            raise IndependencePreconditionsUnmet(facts={"ske_designee_missing": 1})
        if ske_contact_id is not None and ske_contact_id not in ske:
            raise DomainInvalid(facts={"field": "ske_contact_id"})
        # DEC-429 (L2): only a service the firm provides the client outside the attest family.
        if service_code not in await _services(tx.session, ref):
            raise DomainInvalid(facts={"field": "service_code"})
        # The evaluation decision is the engagement partner's: whoever holds the conclusion
        # here (the matrix, through `authorise`'s layers; never a role compared here).
        decides = CONCLUDE in await allowed_actions(ctx, ref.resource(), (CONCLUDE,))
        if status != "pending" and not decides:
            raise Forbidden(NAS, "role")
        row_id = (
            await tx.session.execute(
                select(nas_rows.c.id).where(
                    nas_rows.c.engagement_id == ref.id,
                    nas_rows.c.service_code == service_code,
                )
            )
        ).scalar_one_or_none()
        if row_id is not None and not decides:
            # DEC-429 (L2): once the partner decided a row, a preparer cannot reopen it.
            latest = (
                await tx.session.execute(
                    select(nas_events.c.status)
                    .where(nas_events.c.nas_id == row_id)
                    .order_by(nas_events.c.seq.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest is not None and latest != "pending":
                raise NasDecided(facts={"nas_id": str(row_id)})
        if row_id is None:
            row_id = uuid4()
            await tx.session.execute(
                insert(nas_rows).values(
                    id=row_id,
                    tenant_id=ctx.tenant_id,
                    engagement_id=engagement_id,
                    service_code=service_code,
                    created_by=ctx.user_id,
                )
            )
        event_id = uuid4()
        evaluation = (evaluation or "").strip() or None
        safeguards = (safeguards or "").strip() or None
        await tx.session.execute(
            insert(nas_events).values(
                id=event_id,
                tenant_id=ctx.tenant_id,
                nas_id=row_id,
                provided=provided,
                status=status,
                evaluation_sealed=(
                    await _seal(ctx.tenant, evaluation, "nas.evaluation", event_id)
                    if evaluation
                    else None
                ),
                safeguards_sealed=(
                    await _seal(ctx.tenant, safeguards, "nas.safeguards", event_id)
                    if safeguards
                    else None
                ),
                ske_contact_id=ske_contact_id or ske[0],
                recorded_by=ctx.user_id,
            )
        )
        tx.record(
            "nas.evaluated",
            target=Target("engagement", engagement_id),
            after=Ref(nas_id=row_id, event_id=event_id),
        )
        latest = (
            (await tx.session.execute(select(nas_events).where(nas_events.c.id == event_id)))
            .mappings()
            .one()
        )
        return await _nas_row(ctx.tenant, service_code, dict(latest))


# --- breaches (AC-28) ---------------------------------------------------------------------------


async def _breach_view(
    tenant: TenantContext, session: AsyncSession, breach_id: UUID
) -> BreachView:
    b = (
        (await session.execute(select(breaches).where(breaches.c.id == breach_id)))
        .mappings()
        .one()
    )
    rows = (
        (
            await session.execute(
                select(breach_events)
                .where(breach_events.c.breach_id == breach_id)
                .order_by(breach_events.c.recorded_at, breach_events.c.id)
            )
        )
        .mappings()
        .all()
    )
    events = [BreachEvent("logged", None, b["logged_by"], b["logged_at"])]
    for r in rows:
        events.append(
            BreachEvent(
                r["kind"],
                await _open(tenant, r["note_sealed"], "independence_breach_event.note", r["id"]),
                r["recorded_by"],
                r["recorded_at"],
            )
        )
    kinds = {r["kind"] for r in rows}
    return BreachView(
        breach_id,
        b["engagement_id"],
        await _open(tenant, b["description_sealed"], "independence_breach.description", breach_id)
        or "",
        b["user_id"],
        events,
        all(k in kinds for k in BREACH_STEPS),
    )


async def log_breach(
    ctx: AuthContext, engagement_id: UUID, *, description: str, user_id: UUID | None
) -> BreachView:
    """`independence_breach.logged`: the G2 banner stays until the three events (AC-28)."""
    _live_human(ctx, BREACH)
    kept = description.strip()
    if not kept:
        raise DomainInvalid(facts={"field": "description"})
    if user_id is not None:
        person = await member_facts(ctx.tenant, user_id)
        if person is None or person.client:
            raise DomainInvalid(facts={"field": "user_id"})
    async with uow(ctx.tenant) as tx:
        await _writable(tx, ctx, engagement_id, BREACH)
        breach_id = uuid4()
        await tx.session.execute(
            insert(breaches).values(
                id=breach_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                description_sealed=await _seal(
                    ctx.tenant, kept, "independence_breach.description", breach_id
                ),
                user_id=user_id,
                logged_by=ctx.user_id,
            )
        )
        tx.record(
            "independence_breach.logged",
            target=Target("engagement", engagement_id),
            after=Ref(breach_id=breach_id),
        )
        return await _breach_view(ctx.tenant, tx.session, breach_id)


async def add_breach_event(
    ctx: AuthContext,
    engagement_id: UUID,
    breach_id: UUID,
    *,
    kind: BreachKind,
    note: str | None,
) -> BreachView:
    """One insert-only event per kind (409 `illegal_transition` for a repeat)."""
    _live_human(ctx, BREACH)
    async with uow(ctx.tenant) as tx:
        await _writable(tx, ctx, engagement_id, BREACH)
        owner = (
            await tx.session.execute(
                select(breaches.c.engagement_id).where(breaches.c.id == breach_id)
            )
        ).scalar_one_or_none()
        if owner != engagement_id:
            raise NotFound("independence_breach")
        done = (
            await tx.session.execute(
                select(breach_events.c.id).where(
                    breach_events.c.breach_id == breach_id, breach_events.c.kind == kind
                )
            )
        ).first()
        if done is not None:
            raise IllegalTransition(facts={"breach_id": str(breach_id), "kind": kind})
        event_id = uuid4()
        kept = (note or "").strip() or None
        await tx.session.execute(
            insert(breach_events).values(
                id=event_id,
                tenant_id=ctx.tenant_id,
                breach_id=breach_id,
                kind=kind,
                note_sealed=(
                    await _seal(ctx.tenant, kept, "independence_breach_event.note", event_id)
                    if kept
                    else None
                ),
                recorded_by=ctx.user_id,
            )
        )
        tx.record(
            "independence_breach.updated",
            target=Target("engagement", engagement_id),
            after=Ref(breach_id=breach_id, event_id=event_id),
        )
        view = await _breach_view(ctx.tenant, tx.session, breach_id)
        if view.resolved and await _g2_after(tx.session, engagement_id):
            tx.emit(GateMet(engagement_id=engagement_id, gate="G2"))
        return view


async def _g2_after(session: AsyncSession, engagement_id: UUID) -> bool:
    if await open_breach_ids(session, engagement_id):
        return False
    latest = await latest_conclusion(session, engagement_id)
    return latest is not None and latest.option in POSITIVE


# --- the conclusion (AC-18, AC-19, AC-20) -------------------------------------------------------


async def conclude_independence(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    option: Option,
    safeguards: str | None,
) -> ConclusionView:
    """The engagement partner's conclusion with fresh MFA (matrix), by a live person (here), once
    the preconditions hold; one insert-only row (`actor_kind = 'human'` CHECK, INV-1)."""
    _live_human(ctx, CONCLUDE)
    concluder = await member_facts(ctx.tenant, ctx.user_id)
    if concluder is None or concluder.client or concluder.level != "partner":
        raise Forbidden(CONCLUDE, "role")
    kept = (safeguards or "").strip() or None
    if option == "independent_with_safeguards" and kept is None:
        raise DomainInvalid(facts={"field": "safeguards"})
    try:
        view = await _conclude(ctx, engagement_id, option, kept)
    except IntegrityError as exc:
        # ED-117: a conclusion racing another on the same newest one loses on the one-successor
        # chain; the unit of work rolled back, nothing of this conclusion remains (DEC-461).
        if _constraint(exc) not in _ONE_SUCCESSOR:
            raise
        raise ConclusionSuperseded(facts={"engagement_id": str(engagement_id)}) from None
    if view is None:  # never: the row was just written in this unit of work
        raise NotFound("independence_conclusion")
    return view


async def _conclude(
    ctx: AuthContext, engagement_id: UUID, option: Option, kept: str | None
) -> ConclusionView | None:
    async with uow(ctx.tenant) as tx:
        ref = await _writable(tx, ctx, engagement_id, CONCLUDE)
        facts = await _facts(ctx, tx.session, ref)
        blockers = _blockers(
            facts, engagement_id, with_breaches=False, hidden=await _hidden(ctx, facts)
        )
        if blockers:
            raise IndependencePreconditionsUnmet(facts=_counts(blockers))
        if ctx.mfa_at is None:  # the matrix asked for it already; the row records when
            raise Forbidden(CONCLUDE, "condition")
        previous = await latest_conclusion(tx.session, engagement_id)
        conclusion_id = uuid4()
        await tx.session.execute(
            insert(conclusions).values(
                id=conclusion_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                option=option,
                safeguards_sealed=(
                    await _seal(ctx.tenant, kept, "independence_conclusion", conclusion_id)
                    if kept
                    else None
                ),
                concluded_by=ctx.user_id,
                mfa_verified_at=ctx.mfa_at,
                supersedes_id=previous.id if previous is not None else None,
            )
        )
        tx.record(
            "independence.concluded",
            target=Target("engagement", engagement_id),
            after=Ref(conclusion_id=conclusion_id),
        )
        tx.emit(
            IndependenceConcluded(
                engagement_id=engagement_id, conclusion_id=conclusion_id, option=option
            )
        )
        if option in POSITIVE and not facts.breaches:
            tx.emit(GateMet(engagement_id=engagement_id, gate="G2"))
        return await _conclusion_view(ctx.tenant, tx.session, engagement_id)
