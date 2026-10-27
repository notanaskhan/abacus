"""ENG-05 team and roles (P-07-T30; P-07 §3.5 Story 5.2, §4.2 M4; SPEC-332; DEC-327).

- **Roster:** the firm team with budget hours, the portal flag, when each person joined and their
  independence confirmation for this engagement (`requested`, `confirmed`, `declined`).
- **Team approval:** the engagement partner approves the current team (human-only, an
  insert-only row with the sha256 of the member set); the footer reads who approved it, when,
  whether the team changed since and who joined since.
- **EQR:** the engagement quality reviewer is never on the team. Each candidate's eligibility is
  computed from checks: `not_on_team`, `cooling_off` (not the engagement partner on an engagement
  of this client whose period ended in the two years before this one's), `competence` (how many
  engagements of this service line the person served as partner or EQR; zero is not assessed,
  since a firm new to Accrued has no history here), `independence` (a decline on this engagement
  fails; otherwise pending until they confirm, which G2 enforces on their work) and `capacity`
  (a placeholder, not assessed). Any failing check makes the candidate not eligible.
- **EQR eligibility approval:** by the quality owner (`eqr.approve_eligibility`), never the
  engagement partner (409 `eqr_approver_is_ep`); an insert-only row with the checks and result.
- **Confirmation requests:** a person asks members whose confirmation is still requested or
  declined to confirm; each is audited and notified through `independence.reminded` (P-07-T47).

Every write is one unit of work with its audit event, after `authorise` (INV-5).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import func, select, text, update

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.engagements.events import EqrEligibilityApproved, IndependenceReminded
from abacus.modules.engagements.models import Engagement, IndependenceConfirmation
from abacus.modules.engagements.repository import confirmations_of
from abacus.modules.engagements.service import EngagementRef, get_ref, lock_ref
from abacus.modules.engagements.team_errors import (
    EqrApprovalRequired,
    EqrApproverIsEp,
    EqrApproverOnEngagement,
    EqrNotEligible,
    EqrOnTeam,
    TeamChanged,
)
from abacus.modules.identity.api import (
    EQR_ROLE,
    AuthContext,
    Forbidden,
    MemberDetail,
    candidates,
    engagements_served,
    member_details,
    names_of,
    replace_eqr,
    set_member_portal,
    team_standing,
)
from abacus.modules.identity.api import authorise as _authorise

CheckCode = Literal["not_on_team", "cooling_off", "competence", "independence", "capacity"]
CheckResult = Literal["pass", "fail", "pending", "not_assessed"]
Eligibility = Literal["eligible", "not_eligible"]
COOLING_OFF_YEARS: Final = 2


class TeamApproved(DomainEvent):
    """The engagement partner approved the team (P-07 §4.6). Identifiers only."""

    event_type: ClassVar[str] = "team.approved"

    engagement_id: Annotated[UUID, classified("internal")]
    approval_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class RosterMember:
    user_id: UUID
    display_name: str
    role: str
    budget_hours: Decimal | None
    shown_on_portal: bool
    proposed_at: datetime | None
    independence: str | None


@dataclass(frozen=True)
class TeamApproval:
    engagement_id: UUID
    member_set_hash: str  # the current team's, sent back with an approval (stale: 409)
    approved_by: UUID | None
    approved_by_name: str | None
    approved_at: datetime | None
    changed: bool
    added_since: list[UUID]


@dataclass(frozen=True)
class Check:
    code: CheckCode
    result: CheckResult
    count: int | None = None
    year: int | None = None


@dataclass(frozen=True)
class Candidate:
    user_id: UUID
    display_name: str
    eligibility: Eligibility
    checks: list[Check]
    current: bool = False


@dataclass(frozen=True)
class EqrApproval:
    id: UUID
    engagement_id: UUID
    candidate_user_id: UUID
    result: Eligibility
    checks: list[Check]
    approved_by: UUID
    approved_at: datetime


# --- Roster -------------------------------------------------------------------------------------


async def _confirmations(tenant: TenantContext, engagement_id: UUID) -> dict[UUID, str]:
    async with tenant_session(tenant) as session:
        rows = await confirmations_of(session, engagement_id)
    return {row.user_id: row.status for row in rows}


def _team_rows(details: list[MemberDetail]) -> list[MemberDetail]:
    """The team proper: the EQR is never on it (DEC-327)."""
    return [d for d in details if d.role != EQR_ROLE]


def member_set_hash(details: list[MemberDetail]) -> str:
    """The sha256 of the team's sorted `user_id:role` lines (what an approval approves)."""
    lines = sorted(f"{d.user_id}:{d.role}" for d in _team_rows(details))
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _firm_only(ctx: AuthContext) -> None:
    """The internal roster (roles, hours, independence answers, approvers) is never a client's:
    a client principal holds `engagement.read_metadata` for its own engagement (SPEC-020), so it
    is refused here before anything is read (security review; a POR-02 projection would be a
    separate, names-only read filtered on `shown_on_portal`)."""
    if ctx.client:
        raise Forbidden("engagement.read_metadata", "role")


async def team_of(ctx: AuthContext, engagement_id: UUID) -> list[RosterMember]:
    """The team routes' roster (`engagement.read_metadata`); never a client principal's."""
    _firm_only(ctx)
    ref = await get_ref(ctx, engagement_id)
    await _authorise(ctx, "engagement.read_metadata", ref.resource())
    return await roster(ctx, engagement_id)


async def roster(ctx: AuthContext, engagement_id: UUID) -> list[RosterMember]:
    """After `authorise(engagement.read_metadata)` by the caller."""
    details = await member_details(ctx.tenant, engagement_id)
    names = await names_of([d.user_id for d in details])
    answered = await _confirmations(ctx.tenant, engagement_id)
    return [
        RosterMember(
            d.user_id,
            names.get(d.user_id, ""),
            d.role,
            d.budget_hours,
            d.shown_on_portal,
            d.proposed_at,
            answered.get(d.user_id),
        )
        for d in details
    ]


# --- Team approval ------------------------------------------------------------------------------

_LATEST_APPROVAL = text(
    "SELECT id, approved_by, approved_at, member_set_hash FROM team_approvals "
    "WHERE engagement_id = :e ORDER BY approved_at DESC, id DESC LIMIT 1"
)
_APPROVE = text(
    "INSERT INTO team_approvals (tenant_id, engagement_id, approved_by, member_set_hash) "
    "VALUES (:t, :e, :by, :hash) RETURNING id"
)


async def _approval_of(tenant: TenantContext, engagement_id: UUID) -> TeamApproval:
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST_APPROVAL, {"e": engagement_id})).one_or_none()
    details = await member_details(tenant, engagement_id)
    current = member_set_hash(details)
    if latest is None:
        return TeamApproval(engagement_id, current, None, None, None, False, [])
    approved_at = cast(datetime, latest.approved_at)
    added = [
        d.user_id
        for d in _team_rows(details)
        if d.proposed_at is not None and d.proposed_at > approved_at
    ]
    by = cast(UUID, latest.approved_by)
    names = await names_of([by])
    return TeamApproval(
        engagement_id,
        current,
        by,
        names.get(by),
        approved_at,
        current != str(latest.member_set_hash),
        sorted(added, key=str),
    )


async def team_approval(ctx: AuthContext, engagement_id: UUID) -> TeamApproval:
    """ENG-05's footer: "Team approved by {EP} · {date} · changes since: + {person}"."""
    _firm_only(ctx)
    ref = await get_ref(ctx, engagement_id)
    await _authorise(ctx, "engagement.read_metadata", ref.resource())
    return await _approval_of(ctx.tenant, engagement_id)


async def approve_team(
    ctx: AuthContext, engagement_id: UUID, member_set_hash_seen: str
) -> TeamApproval:
    """Human-only (INV-1), fresh MFA: the engagement partner approves exactly the team they saw.
    `member_set_hash_seen` is the `member_set_hash` of the read they approved from; a team that
    changed since answers 409 `stale_version` and nothing is written."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _authorise(ctx, "team.approve", ref.resource())
        details = await member_details(ctx.tenant, engagement_id)
        if member_set_hash(details) != member_set_hash_seen:
            raise TeamChanged(facts={"engagement_id": str(engagement_id)})
        approval_id = (
            await tx.session.execute(
                _APPROVE,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "by": ctx.user_id,
                    "hash": member_set_hash(details),
                },
            )
        ).scalar_one()
        tx.record("team.approved", target=Target("engagement", engagement_id))
        tx.emit(TeamApproved(engagement_id=engagement_id, approval_id=approval_id))
    return await _approval_of(ctx.tenant, engagement_id)


# --- The portal flag ----------------------------------------------------------------------------


async def set_portal_visibility(
    ctx: AuthContext, engagement_id: UUID, user_id: UUID, shown: bool
) -> None:
    """POR-02's team card shows this member or not (`engagement.update`)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _authorise(ctx, "engagement.update", ref.resource())
        await set_member_portal(tx, engagement_id, user_id, shown)


# --- EQR eligibility ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Target:
    id: UUID
    client_id: UUID
    service_line: str
    period_end: date


async def _target(tenant: TenantContext, engagement_id: UUID) -> _Target:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                select(
                    Engagement.id,
                    Engagement.client_id,
                    Engagement.service_line,
                    Engagement.fiscal_period_end,
                ).where(Engagement.id == engagement_id)
            )
        ).one_or_none()
    if row is None:
        raise NotFound("engagement")
    return _Target(row.id, row.client_id, str(row.service_line), row.fiscal_period_end)


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


async def eligibility_checks(
    tenant: TenantContext, target: _Target, user_id: UUID, *, confirmation: str | None
) -> list[Check]:
    """The five checks for one candidate on `target` (see the module docstring)."""
    standing = await team_standing(tenant, target.id, user_id)
    held = await engagements_served(tenant, user_id)
    served = held.as_partner_or_eqr - {target.id}
    as_partner = held.as_partner - {target.id}
    window_start = _years_before(target.period_end, COOLING_OFF_YEARS)
    cooling_year: int | None = None
    competence = 0
    if served:
        async with tenant_session(tenant) as session:
            rows = (
                await session.execute(
                    select(
                        Engagement.id,
                        Engagement.client_id,
                        Engagement.service_line,
                        Engagement.fiscal_period_end,
                    ).where(Engagement.id.in_(sorted(served, key=str)))
                )
            ).all()
        for row in rows:
            if str(row.service_line) == target.service_line:
                competence += 1
            if (
                row.id in as_partner
                and row.client_id == target.client_id
                and window_start < row.fiscal_period_end <= target.period_end
            ):
                year = row.fiscal_period_end.year
                cooling_year = year if cooling_year is None else max(cooling_year, year)
    on_team = standing in ("partner", "team")
    return [
        Check("not_on_team", "fail" if on_team else "pass"),
        Check("cooling_off", "fail" if cooling_year is not None else "pass", year=cooling_year),
        Check("competence", "pass" if competence else "not_assessed", count=competence),
        Check("independence", _independence(confirmation)),
        Check("capacity", "not_assessed"),
    ]


def _independence(confirmation: str | None) -> CheckResult:
    if confirmation == "confirmed":
        return "pass"
    if confirmation == "declined":
        return "fail"
    return "pending"  # requested, or not asked yet: asked on assignment, G2 holds their work


def _eligibility(checks: list[Check]) -> Eligibility:
    return "not_eligible" if any(c.result == "fail" for c in checks) else "eligible"


async def eqr_candidates(ctx: AuthContext, engagement_id: UUID) -> list[Candidate]:
    """ENG-05 c: the current EQR first, then every active staff member not on the engagement and
    not walled from its client, each with its checks."""
    ref = await get_ref(ctx, engagement_id)
    await _authorise(ctx, "eqr.assign", ref.resource())
    target = await _target(ctx.tenant, engagement_id)
    details = await member_details(ctx.tenant, engagement_id)
    current = [d.user_id for d in details if d.role == EQR_ROLE]
    answered = await _confirmations(ctx.tenant, engagement_id)
    names = await names_of(current)
    people = [(u, names.get(u, ""), True) for u in current] + [
        (c.user_id, c.display_name, False)
        for c in await candidates(ctx.tenant, engagement_id, ref.client_id)
    ]
    found: list[Candidate] = []
    for user_id, name, is_current in people:
        checks = await eligibility_checks(
            ctx.tenant, target, user_id, confirmation=answered.get(user_id)
        )
        found.append(Candidate(user_id, name, _eligibility(checks), checks, is_current))
    return found


def _failing(checks: list[Check]) -> dict[str, object]:
    return {c.code: "fail" for c in checks if c.result == "fail"}


async def assign_eqr(ctx: AuthContext, engagement_id: UUID, user_id: UUID) -> list[Check]:
    """Make `user_id` the engagement's EQR, replacing any other. 409 `eqr_on_team` for someone on
    the team; 409 `eqr_not_eligible` with the failing checks; 404 for someone who is not an
    active, unwalled staff member of the firm."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _authorise(ctx, "eqr.assign", ref.resource())
        standing = await team_standing(ctx.tenant, engagement_id, user_id)
        if standing == "client":
            raise NotFound("person")
        if standing in ("partner", "team"):
            raise EqrOnTeam(facts={"user_id": str(user_id)})
        # Who may be a candidate at all (active staff, not walled, not hidden) before any check,
        # so a walled or unknown person is 404 and never a 409 carrying facts about them.
        if standing != "eqr" and user_id not in await _candidate_ids(ctx, engagement_id, ref):
            raise NotFound("person")
        target = await _target(ctx.tenant, engagement_id)
        answered = await _confirmations(ctx.tenant, engagement_id)
        checks = await eligibility_checks(
            ctx.tenant, target, user_id, confirmation=answered.get(user_id)
        )
        if _eligibility(checks) == "not_eligible":
            raise EqrNotEligible(facts=_failing(checks))
        if _needs_approval(checks) and not await _approved(ctx.tenant, engagement_id, user_id):
            raise EqrApprovalRequired(facts={"user_id": str(user_id)})
        if standing == "eqr":
            return checks  # already the EQR: nothing to change
        await replace_eqr(tx, ctx, engagement_id, ref.client_id, user_id)
    return checks


async def _candidate_ids(ctx: AuthContext, engagement_id: UUID, ref: EngagementRef) -> set[UUID]:
    return {c.user_id for c in await candidates(ctx.tenant, engagement_id, ref.client_id)}


def _needs_approval(checks: list[Check]) -> bool:
    """Competence the history cannot show (`not_assessed`) is the quality owner's judgement: an
    eligible approval of the candidate must exist before they are assigned (security review).
    `capacity` is a placeholder and never asks for one."""
    return any(c.code == "competence" and c.result == "not_assessed" for c in checks)


_LATEST_EQR_APPROVAL = text(
    "SELECT result FROM eqr_eligibility_approvals WHERE engagement_id = :e "
    "AND candidate_user_id = :c ORDER BY approved_at DESC, id DESC LIMIT 1"
)


async def _approved(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> bool:
    """The quality owner's latest approval of this candidate here reads eligible."""
    async with tenant_session(tenant) as session:
        result = await session.scalar(_LATEST_EQR_APPROVAL, {"e": engagement_id, "c": user_id})
    return result == "eligible"


_APPROVE_EQR = text(
    "INSERT INTO eqr_eligibility_approvals "
    "(tenant_id, engagement_id, candidate_user_id, checks, result, approved_by) "
    "VALUES (:t, :e, :c, CAST(:checks AS jsonb), :result, :by) RETURNING id, approved_at"
)


async def approve_eqr_eligibility(
    ctx: AuthContext, engagement_id: UUID, candidate_user_id: UUID
) -> EqrApproval:
    """Human-only: the quality owner approves (or records as not eligible) an EQR candidate.
    Never someone with any role on the engagement: its partner (409 `eqr_approver_is_ep`), or
    a manager, team member, specialist or its EQR (409 `eqr_approver_on_engagement`); never the
    candidate themself (422)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _authorise(ctx, "eqr.approve_eligibility", ref.resource())
        approver = await team_standing(ctx.tenant, engagement_id, ctx.user_id)
        if approver == "partner":
            raise EqrApproverIsEp
        if approver != "none":
            raise EqrApproverOnEngagement
        if candidate_user_id == ctx.user_id:
            raise DomainInvalid(facts={"field": "candidate_user_id"})
        standing = await team_standing(ctx.tenant, engagement_id, candidate_user_id)
        if standing != "eqr" and candidate_user_id not in await _candidate_ids(
            ctx, engagement_id, ref
        ):
            raise NotFound("person")
        target = await _target(ctx.tenant, engagement_id)
        answered = await _confirmations(ctx.tenant, engagement_id)
        checks = await eligibility_checks(
            ctx.tenant, target, candidate_user_id, confirmation=answered.get(candidate_user_id)
        )
        result = _eligibility(checks)
        row = (
            await tx.session.execute(
                _APPROVE_EQR,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "c": candidate_user_id,
                    "checks": _checks_json(checks),
                    "result": result,
                    "by": ctx.user_id,
                },
            )
        ).one()
        tx.record(
            "eqr.eligibility_approved",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=candidate_user_id),
        )
        tx.emit(EqrEligibilityApproved(engagement_id=engagement_id, user_id=candidate_user_id))
    return EqrApproval(
        row.id, engagement_id, candidate_user_id, result, checks, ctx.user_id, row.approved_at
    )


def _checks_json(checks: list[Check]) -> str:
    return json.dumps(
        [{"code": c.code, "result": c.result, "count": c.count, "year": c.year} for c in checks]
    )


# --- Confirmation requests ----------------------------------------------------------------------

_OPEN: Final = frozenset({"requested", "declined"})


# P-07-T47: the EQR eligibility gate (`human_gates.eqr_eligibility_due`) asks the same questions.
eqr_target = _target
needs_eqr_approval = _needs_approval
eqr_approved = _approved


async def remind_independence(
    ctx: AuthContext, engagement_id: UUID, user_ids: list[UUID]
) -> list[UUID]:
    """ENG-05 "Send confirmation request" / CLI-08 "Send reminder", sent by the person clicking:
    each named member must have a confirmation still requested or declined (422 otherwise)."""
    wanted = list(dict.fromkeys(user_ids))
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _authorise(ctx, "independence.remind", ref.resource())
        rows = await tx.session.execute(
            select(IndependenceConfirmation.user_id, IndependenceConfirmation.status).where(
                IndependenceConfirmation.engagement_id == engagement_id,
                IndependenceConfirmation.user_id.in_(wanted),
            )
        )
        open_ = {r.user_id for r in rows if r.status in _OPEN}
        for user_id in wanted:
            if user_id not in open_:
                raise DomainInvalid(facts={"user_id": str(user_id)})
        # P-07-T41: CLI-08 shows how often each member was reminded.
        await tx.session.execute(
            update(IndependenceConfirmation)
            .where(
                IndependenceConfirmation.engagement_id == engagement_id,
                IndependenceConfirmation.user_id.in_(wanted),
            )
            .values(
                reminder_count=IndependenceConfirmation.reminder_count + 1,
                last_reminded_at=func.clock_timestamp(),
            )
        )
        for user_id in wanted:
            tx.record(
                "independence.reminded",
                target=Target("engagement", engagement_id),
                after=Ref(user_id=user_id),
            )
            # P-07-T47: the reminder is its own kind (`independence_reminder`, C16).
            tx.emit(
                IndependenceReminded(
                    engagement_id=engagement_id, user_id=user_id, by_user=ctx.user_id
                )
            )
    return wanted
