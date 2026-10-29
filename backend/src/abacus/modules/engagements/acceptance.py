"""Acceptance and continuance, live (P-07-T35; CLI-07; SPEC-332 AC-1 to AC-10; DEC-372).

One record per engagement, pinned to a version of the firm's questionnaire template (database
content). Prepared by the engagement partner and managers: answers and the risk rating, flags a
person writes (with source references), manual checks asked of a named person and completed only
by them, then "Send to partner". The engagement partner alone decides, with fresh MFA, one of
three options with a rationale; Accept with conditions carries its conditions. A High-risk record
waits for a risk-partner review completed by another partner the EP named. The decision row is
insert-only and locks the record; the engagement moves Prospect → Accepted or Declined in the same
unit of work, and G1 becomes met on accept (`acceptance_tables.g1_decision`).

Every write: a live person (never an agent, the platform, a client or a support session), the
matrix action on the engagement, one unit of work, one audit event. Free text (answers,
flag title and body, notes, the rationale, conditions) is sealed per tenant, each bound to its
own row. `decide_acceptance` is named only here and in the route (banned pattern ACCEPT-001).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.acceptance_tables import (
    LOCKED,
    answers,
    condition_events,
    condition_rows,
    decisions,
    flags,
    manual_checks,
    records,
    reviews,
    template_versions,
    templates,
)
from abacus.modules.engagements.events import AcceptanceReviewRequested
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.record import GateMet
from abacus.modules.engagements.service import EngagementRef, get_ref, lock_ref
from abacus.modules.engagements.transitions import IllegalTransition, transition
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    engagement_role_of,
    hidden_clients,
    member_facts,
    team_standing,
)

READ: Final = "acceptance.read"
PREPARE: Final = "acceptance.prepare"
REQUEST_REVIEW: Final = "acceptance.request_review"
COMPLETE_REVIEW: Final = "acceptance.complete_review"
DECIDE: Final = "acceptance.decide"
ACTIONS: Final = (READ, PREPARE, REQUEST_REVIEW, DECIDE)
# Who may be asked to complete a manual check: the people who hold `acceptance.prepare` here.
_PREPARERS: Final = frozenset({"engagement_partner", "manager", "client_service"})

Kind = Literal["new_client", "new_engagement_existing_client", "continuance"]
Option = Literal["accept", "accept_with_conditions", "decline"]
AnswerValue = str | int | bool | None


# --- errors (`error-codes.yaml`) ----------------------------------------------------------------


class DecisionLocked(DomainConflict):
    """The acceptance record is decided and locked: nothing on it changes any more."""

    code = "decision_locked"


class RationaleRequired(DomainInvalid):
    """A decision needs a rationale; Accept with conditions needs a condition (`facts.field`)."""

    code = "rationale_required"


class AcceptanceNotReady(DomainConflict):
    """Not ready for decision: a manual check is open (`facts.section`, `facts.open_checks`), or
    the record has not been sent to the partner."""

    code = "acceptance_not_ready"


class ReviewRequired(DomainConflict):
    """A High-risk record needs a completed risk-partner review before the decision."""

    code = "review_required"


class AcceptanceStale(DomainConflict):
    """The record (or the section) changed since `seen_version` was read."""

    code = "stale_version"


class AcceptanceSent(DomainConflict):
    """The record was sent to the partner: its answers, risk rating and manual checks are
    frozen (DEC-375)."""

    code = "acceptance_sent"


class AcceptanceTemplateMissing(DomainConflict):
    """The firm has no acceptance questionnaire for the engagement type's family (`facts.family`):
    templates are database content, loaded before acceptance can start."""

    code = "acceptance_template_missing"


# --- outbox events (identifiers and codes only) ------------------------------------------------


class AcceptanceSentToPartner(DomainEvent):
    event_type: ClassVar[str] = "acceptance.sent_to_partner"

    engagement_id: Annotated[UUID, classified("internal")]
    record_id: Annotated[UUID, classified("internal")]


class AcceptanceDecided(DomainEvent):
    event_type: ClassVar[str] = "acceptance.decided"

    engagement_id: Annotated[UUID, classified("internal")]
    record_id: Annotated[UUID, classified("internal")]
    option: Annotated[str, classified("internal")]


# --- views ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    kind: str
    id: UUID


@dataclass(frozen=True)
class ManualCheck:
    section_code: str
    requested_of: UUID
    requested_by: UUID
    requested_at: datetime
    completed_by: UUID | None = None
    completed_at: datetime | None = None
    note: str | None = None


@dataclass(frozen=True)
class AcceptanceSection:
    code: str
    title: str
    answer_state: str
    answers: dict[str, AnswerValue]
    manual_check: ManualCheck | None
    version: int


@dataclass(frozen=True)
class AcceptanceFlag:
    id: UUID
    severity: str
    title: str
    body: str
    sources: list[SourceRef]
    authored_by: UUID
    authored_at: datetime


@dataclass(frozen=True)
class Condition:
    id: UUID
    text: str
    assignee_user_id: UUID
    due_on: date | None = None
    completed_by: UUID | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class Decision:
    option: str
    rationale: str
    decided_by: UUID
    decided_at: datetime


@dataclass(frozen=True)
class RiskReview:
    partner_id: UUID
    requested_by: UUID
    requested_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True)
class Prior:
    record_id: UUID
    engagement_id: UUID
    option: str | None = None
    decided_at: datetime | None = None
    conditions: list[Condition] = field(default_factory=list[Condition])
    independence: str | None = None  # P-07-T41's conclusion; none before it


@dataclass(frozen=True)
class RecordView:
    id: UUID
    engagement_id: UUID
    client_id: UUID
    kind: str
    status: str
    template_version_id: UUID
    template_name: str
    prepared_by: UUID
    risk_rating: str | None
    sent_to_partner_at: datetime | None
    sent_to_partner_by: UUID | None
    sections: list[AcceptanceSection]
    flags: list[AcceptanceFlag]
    decision: Decision | None
    conditions: list[Condition]
    risk_partner_review: RiskReview | None
    prior: Prior | None
    version: int
    allowed_actions: list[str]


@dataclass(frozen=True)
class NewCondition:
    text: str
    assignee_user_id: UUID
    due_on: date | None = None


# --- sealing ------------------------------------------------------------------------------------


def _binding(kind: str, *parts: object) -> str:
    """What a sealed value is bound to: its own row and field, so it opens only there."""
    return hashlib.sha256(":".join([kind, *(str(p) for p in parts)]).encode()).hexdigest()


async def _seal(tenant: TenantContext, text: str, kind: str, *parts: object) -> bytes:
    return await seal(tenant.tenant_id, text.encode(), _binding(kind, *parts))


async def _open(tenant: TenantContext, sealed: bytes | None, kind: str, *parts: object) -> str:
    if sealed is None:
        return ""
    return (await open_sealed(tenant.tenant_id, sealed, _binding(kind, *parts))).decode()


# --- guards -------------------------------------------------------------------------------------


def _live_human(ctx: AuthContext, action: str) -> None:
    """INV-1 (`require_live_human`): a person's own act, never an agent, the platform, a client
    principal or a break-glass support session."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _not_client_service(ctx: AuthContext, engagement_id: UUID) -> None:
    """Client service holds `acceptance.prepare` only to complete a check asked of them
    (DEC-326): every other preparing write is refused to them."""
    if await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) == "client_service":
        raise Forbidden(PREPARE, "role")


async def _record_for_update(tx: UnitOfWork, engagement_id: UUID) -> RowMapping:
    row = (
        (
            await tx.session.execute(
                select(records).where(records.c.engagement_id == engagement_id).with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound("acceptance_record")
    return row


# The risk rating's position, for an audit reference (identifiers and integers only, DEC-375).
RISK_CODES: Final = (None, "low", "moderate", "high")


def _draft_record(row: RowMapping) -> None:
    """DEC-375 (security review H1): answers, the risk rating and manual checks change only
    while the record is a Draft; the database holds the same (0165)."""
    _open_record(row)
    if row["status"] != "draft":
        raise AcceptanceSent(facts={"record_id": str(row["id"])})


def _open_record(row: RowMapping) -> None:
    if row["status"] in LOCKED:
        raise DecisionLocked(facts={"record_id": str(row["id"])})


async def _bump(tx: UnitOfWork, record_id: UUID, **values: object) -> int:
    return cast(
        int,
        (
            await tx.session.execute(
                update(records)
                .where(records.c.id == record_id)
                .values(version=records.c.version + 1, **values)
                .returning(records.c.version)
            )
        ).scalar_one(),
    )


async def _writable(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, action: str
) -> tuple[EngagementRef, RowMapping]:
    _live_human(ctx, action)
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, action, ref.resource())
    record = await _record_for_update(tx, engagement_id)
    return ref, record


def _template_sections(raw: object) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in cast(list[dict[str, object]], raw or []):
        code, title = item.get("code"), item.get("title")
        if isinstance(code, str) and isinstance(title, str):
            out.append((code, title))
    return out


async def _sections_of(session: AsyncSession, version_id: UUID) -> list[tuple[str, str]]:
    raw = (
        await session.execute(
            select(template_versions.c.sections).where(template_versions.c.id == version_id)
        )
    ).scalar_one()
    return _template_sections(raw)


# --- read ---------------------------------------------------------------------------------------


async def _conditions(
    session: AsyncSession, tenant: TenantContext, record_id: UUID
) -> list[Condition]:
    rows = (
        (
            await session.execute(
                select(
                    condition_rows,
                    condition_events.c.actor_id.label("completed_by"),
                    condition_events.c.at.label("completed_at"),
                )
                .select_from(
                    condition_rows.outerjoin(
                        condition_events, condition_events.c.condition_id == condition_rows.c.id
                    )
                )
                .where(condition_rows.c.record_id == record_id)
                .order_by(condition_rows.c.position)
            )
        )
        .mappings()
        .all()
    )
    return [
        Condition(
            id=r["id"],
            text=await _open(tenant, r["text_sealed"], "acceptance_condition.text", r["id"]),
            assignee_user_id=r["assignee_user_id"],
            due_on=r["due_on"],
            completed_by=r["completed_by"],
            completed_at=r["completed_at"],
        )
        for r in rows
    ]


async def _decision(
    session: AsyncSession, tenant: TenantContext, record_id: UUID
) -> Decision | None:
    row = (
        (await session.execute(select(decisions).where(decisions.c.record_id == record_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    rationale = await _open(tenant, row["rationale_sealed"], "acceptance_decision", row["id"])
    return Decision(row["option"], rationale, row["decided_by"], row["decided_at"])


async def _review(session: AsyncSession, record_id: UUID) -> RiskReview | None:
    rows = (
        (
            await session.execute(
                select(reviews).where(reviews.c.record_id == record_id).order_by(reviews.c.at)
            )
        )
        .mappings()
        .all()
    )
    current: RiskReview | None = None
    for r in rows:
        if r["event"] == "requested":
            current = RiskReview(r["partner_id"], r["actor_id"], r["at"])
        elif current is not None and r["partner_id"] == current.partner_id:
            current = RiskReview(
                current.partner_id, current.requested_by, current.requested_at, r["at"]
            )
    return current


async def _latest_checks(session: AsyncSession, record_id: UUID) -> dict[str, RowMapping]:
    rows = (
        (
            await session.execute(
                select(manual_checks)
                .where(manual_checks.c.record_id == record_id)
                .order_by(manual_checks.c.requested_at, manual_checks.c.id)
            )
        )
        .mappings()
        .all()
    )
    return {cast(str, r["section_code"]): r for r in rows}  # the newest wins


async def _check_view(tenant: TenantContext, r: RowMapping) -> ManualCheck:
    return ManualCheck(
        section_code=r["section_code"],
        requested_of=r["requested_of"],
        requested_by=r["requested_by"],
        requested_at=r["requested_at"],
        completed_by=r["completed_by"],
        completed_at=r["completed_at"],
        note=(await _open(tenant, r["note_sealed"], "acceptance_manual_check", r["id"]))
        if r["note_sealed"] is not None
        else None,
    )


def _state(answer: RowMapping | None, check: RowMapping | None) -> str:
    if check is not None:
        return "manual_check_open" if check["completed_at"] is None else "manual_check_done"
    return cast(str, answer["state"]) if answer is not None else "pending"


async def _view(
    session: AsyncSession, ctx: AuthContext, row: RowMapping, ref: EngagementRef
) -> RecordView:
    tenant = ctx.tenant
    record_id = cast(UUID, row["id"])
    version = (
        await session.execute(
            select(template_versions.c.sections, templates.c.name)
            .select_from(
                template_versions.join(
                    templates, templates.c.id == template_versions.c.template_id
                )
            )
            .where(template_versions.c.id == row["template_version_id"])
        )
    ).one()
    answer_rows = {
        cast(str, a["section_code"]): a
        for a in (await session.execute(select(answers).where(answers.c.record_id == record_id)))
        .mappings()
        .all()
    }
    checks = await _latest_checks(session, record_id)
    sections: list[AcceptanceSection] = []
    for code, title in _template_sections(version.sections):
        a = answer_rows.get(code)
        c = checks.get(code)
        values: dict[str, AnswerValue] = {}
        if a is not None and a["answers_sealed"] is not None:
            opened = await _open(tenant, a["answers_sealed"], "acceptance_answers", a["id"])
            values = cast(dict[str, AnswerValue], json.loads(opened))
        sections.append(
            AcceptanceSection(
                code=code,
                title=title,
                answer_state=_state(a, c),
                answers=values,
                manual_check=await _check_view(tenant, c) if c is not None else None,
                version=cast(int, a["version"]) if a is not None else 0,
            )
        )
    flag_rows = (
        (
            await session.execute(
                select(flags)
                .where(flags.c.record_id == record_id)
                .order_by(flags.c.authored_at, flags.c.id)
            )
        )
        .mappings()
        .all()
    )
    flag_views = [
        AcceptanceFlag(
            id=f["id"],
            severity=f["severity"],
            title=await _open(tenant, f["title_sealed"], "acceptance_flag.title", f["id"]),
            body=await _open(tenant, f["body_sealed"], "acceptance_flag.body", f["id"]),
            sources=[
                SourceRef(str(s["kind"]), UUID(str(s["id"])))
                for s in cast(list[dict[str, object]], f["source_refs"] or [])
            ],
            authored_by=f["authored_by"],
            authored_at=f["authored_at"],
        )
        for f in flag_rows
    ]
    prior: Prior | None = None
    if row["prior_record_id"] is not None:
        p = (
            (await session.execute(select(records).where(records.c.id == row["prior_record_id"])))
            .mappings()
            .one()
        )
        before = await _decision(session, tenant, p["id"])
        prior = Prior(
            record_id=p["id"],
            engagement_id=p["engagement_id"],
            option=before.option if before is not None else None,
            decided_at=before.decided_at if before is not None else None,
            conditions=await _conditions(session, tenant, p["id"]),
        )
    allowed = await allowed_actions(ctx, ref.resource(), ACTIONS)
    return RecordView(
        id=record_id,
        engagement_id=row["engagement_id"],
        client_id=row["client_id"],
        kind=row["kind"],
        status=row["status"],
        template_version_id=row["template_version_id"],
        template_name=cast(str, version.name),
        prepared_by=row["prepared_by"],
        risk_rating=row["risk_rating"],
        sent_to_partner_at=row["sent_to_partner_at"],
        sent_to_partner_by=row["sent_to_partner_by"],
        sections=sections,
        flags=flag_views,
        decision=await _decision(session, tenant, record_id),
        conditions=await _conditions(session, tenant, record_id),
        risk_partner_review=await _review(session, record_id),
        prior=prior,
        version=row["version"],
        allowed_actions=sorted(allowed),
    )


async def acceptance_record(ctx: AuthContext, engagement_id: UUID) -> RecordView:
    """CLI-07: the record with its sections, checks, flags, decision, conditions and review."""
    _live_human(ctx, READ)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, READ, ref.resource())
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    select(records).where(records.c.engagement_id == engagement_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFound("acceptance_record")
        return await _view(session, ctx, row, ref)


async def _section(ctx: AuthContext, engagement_id: UUID, code: str) -> AcceptanceSection:
    record = await acceptance_record(ctx, engagement_id)
    found = next((s for s in record.sections if s.code == code), None)
    if found is None:
        raise NotFound("acceptance_section")
    return found


# --- prepare ------------------------------------------------------------------------------------


async def update_answers(
    ctx: AuthContext,
    engagement_id: UUID,
    section_code: str,
    *,
    seen_version: int,
    values: Mapping[str, AnswerValue],
    complete: bool,
    risk_rating: str | None,
) -> AcceptanceSection:
    """A section's answers (sealed) and, optionally, the record's risk rating; 409
    `stale_version` when the section changed since `seen_version` (0 for an unanswered one)."""
    async with uow(ctx.tenant) as tx:
        _, record = await _writable(tx, ctx, engagement_id, PREPARE)
        await _not_client_service(ctx, engagement_id)
        _draft_record(record)
        record_id = cast(UUID, record["id"])
        codes = {c for c, _ in await _sections_of(tx.session, record["template_version_id"])}
        if section_code not in codes:
            raise NotFound("acceptance_section")
        existing = (
            (
                await tx.session.execute(
                    select(answers)
                    .where(
                        answers.c.record_id == record_id, answers.c.section_code == section_code
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        current = cast(int, existing["version"]) if existing is not None else 0
        if current != seen_version:
            raise AcceptanceStale(facts={"record_id": str(record_id), "section": section_code})
        state = "complete" if complete else "pending"
        if existing is None:
            answer_id = (
                await tx.session.execute(
                    insert(answers)
                    .values(
                        tenant_id=ctx.tenant_id,
                        record_id=record_id,
                        section_code=section_code,
                        state=state,
                        updated_by=ctx.user_id,
                    )
                    .returning(answers.c.id)
                )
            ).scalar_one()
        else:
            answer_id = cast(UUID, existing["id"])
        sealed = await _seal(
            ctx.tenant, json.dumps(dict(values), sort_keys=True), "acceptance_answers", answer_id
        )
        await tx.session.execute(
            update(answers)
            .where(answers.c.id == answer_id)
            .values(
                answers_sealed=sealed,
                state=state,
                version=answers.c.version + (0 if existing is None else 1),
                updated_by=ctx.user_id,
                updated_at=func.clock_timestamp(),
            )
        )
        extra: dict[str, object] = {}
        before = cast(str | None, record["risk_rating"])
        if risk_rating is not None and risk_rating != before:
            extra["risk_rating"] = risk_rating
        version = await _bump(tx, record_id, **extra)
        after = risk_rating if risk_rating is not None else before
        tx.record(
            "acceptance.answers_updated",
            target=Target("engagement", engagement_id),
            after=Ref(
                record_id=record_id,
                version=version,
                risk_before=RISK_CODES.index(before),
                risk_after=RISK_CODES.index(after),
            ),
        )
    return await _section(ctx, engagement_id, section_code)


async def add_flag(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    severity: str,
    title: str,
    body: str,
    sources: Sequence[SourceRef],
) -> AcceptanceFlag:
    """AC-2: an insert-only flag the caller authored (the CHECK holds `authored_kind`)."""
    async with uow(ctx.tenant) as tx:
        _, record = await _writable(tx, ctx, engagement_id, PREPARE)
        await _not_client_service(ctx, engagement_id)
        _open_record(record)
        flag_id = uuid4()
        await tx.session.execute(
            insert(flags).values(
                id=flag_id,
                tenant_id=ctx.tenant_id,
                record_id=record["id"],
                severity=severity,
                title_sealed=await _seal(ctx.tenant, title, "acceptance_flag.title", flag_id),
                body_sealed=await _seal(ctx.tenant, body, "acceptance_flag.body", flag_id),
                source_refs=[{"kind": s.kind, "id": str(s.id)} for s in sources],
                authored_by=ctx.user_id,
            )
        )
        await _bump(tx, record["id"])
        tx.record(
            "acceptance.flag_added",
            target=Target("engagement", engagement_id),
            after=Ref(flag_id=flag_id),
        )
    record_view = await acceptance_record(ctx, engagement_id)
    return next(f for f in record_view.flags if f.id == flag_id)


async def request_manual_check(
    ctx: AuthContext, engagement_id: UUID, section_code: str, requested_of: UUID
) -> ManualCheck:
    """A manual check asked of a person who may complete it here (engagement partner, manager
    or client service on this engagement); 422 `invalid` for anyone else or a second open
    check on the section."""
    async with uow(ctx.tenant) as tx:
        _, record = await _writable(tx, ctx, engagement_id, PREPARE)
        await _not_client_service(ctx, engagement_id)
        _draft_record(record)
        codes = {c for c, _ in await _sections_of(tx.session, record["template_version_id"])}
        if section_code not in codes:
            raise NotFound("acceptance_section")
        role = await engagement_role_of(ctx.tenant, engagement_id, requested_of)
        if role not in _PREPARERS:
            raise DomainInvalid(facts={"field": "requested_of"})
        open_check = (
            await tx.session.execute(
                select(manual_checks.c.id).where(
                    manual_checks.c.record_id == record["id"],
                    manual_checks.c.section_code == section_code,
                    manual_checks.c.completed_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if open_check is not None:
            raise DomainInvalid(facts={"field": "section_code"})
        check_id = uuid4()
        await tx.session.execute(
            insert(manual_checks).values(
                id=check_id,
                tenant_id=ctx.tenant_id,
                record_id=record["id"],
                section_code=section_code,
                requested_of=requested_of,
                requested_by=ctx.user_id,
            )
        )
        await _bump(tx, record["id"])
        tx.record(
            "acceptance.manual_check_requested",
            target=Target("engagement", engagement_id),
            after=Ref(check_id=check_id, user_id=requested_of),
        )
    found = (await _section(ctx, engagement_id, section_code)).manual_check
    if found is None:
        raise NotFound("manual_check")
    return found


async def complete_manual_check(
    ctx: AuthContext, engagement_id: UUID, section_code: str, note: str | None
) -> ManualCheck:
    """Completed once, only by the person it was asked of (client service included)."""
    async with uow(ctx.tenant) as tx:
        _, record = await _writable(tx, ctx, engagement_id, PREPARE)
        _draft_record(record)
        check = (
            (
                await tx.session.execute(
                    select(manual_checks)
                    .where(
                        manual_checks.c.record_id == record["id"],
                        manual_checks.c.section_code == section_code,
                        manual_checks.c.completed_at.is_(None),
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if check is None:
            raise NotFound("manual_check")
        if check["requested_of"] != ctx.user_id:
            raise Forbidden(PREPARE, "role")
        sealed = (
            await _seal(ctx.tenant, note, "acceptance_manual_check", check["id"]) if note else None
        )
        await tx.session.execute(
            update(manual_checks)
            .where(manual_checks.c.id == check["id"])
            .values(completed_by=ctx.user_id, note_sealed=sealed)
        )
        await _bump(tx, record["id"])
        tx.record(
            "acceptance.manual_check_completed",
            target=Target("engagement", engagement_id),
            after=Ref(check_id=check["id"]),
        )
    found = (await _section(ctx, engagement_id, section_code)).manual_check
    if found is None:
        raise NotFound("manual_check")
    return found


async def send_to_partner(ctx: AuthContext, engagement_id: UUID, seen_version: int) -> RecordView:
    """AC-1, AC-3: Draft → Awaiting partner once every manual check is complete."""
    async with uow(ctx.tenant) as tx:
        _, record = await _writable(tx, ctx, engagement_id, PREPARE)
        await _not_client_service(ctx, engagement_id)
        _open_record(record)
        record_id = cast(UUID, record["id"])
        if record["status"] != "draft":
            raise IllegalTransition(
                facts={"from_status": record["status"], "to_status": "awaiting_partner"}
            )
        if record["version"] != seen_version:
            raise AcceptanceStale(facts={"record_id": str(record_id)})
        open_checks = sorted(
            code
            for code, c in (await _latest_checks(tx.session, record_id)).items()
            if c["completed_at"] is None
        )
        if open_checks:
            raise AcceptanceNotReady(
                facts={"section": open_checks[0], "open_checks": len(open_checks)}
            )
        await _bump(
            tx,
            record_id,
            status="awaiting_partner",
            sent_to_partner_at=func.clock_timestamp(),
            sent_to_partner_by=ctx.user_id,
        )
        tx.record(
            "acceptance.sent_to_partner",
            target=Target("engagement", engagement_id),
            after=Ref(record_id=record_id),
        )
        tx.emit(AcceptanceSentToPartner(engagement_id=engagement_id, record_id=record_id))
    return await acceptance_record(ctx, engagement_id)


async def complete_condition(
    ctx: AuthContext, engagement_id: UUID, condition_id: UUID, note: str | None
) -> Condition:
    """AC-9: an insert-only completion by the assignee or a preparer (client service only for
    their own); 422 `invalid` when it is already complete."""
    async with uow(ctx.tenant) as tx:
        _live_human(ctx, PREPARE)
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, PREPARE, ref.resource())
        found = (
            (
                await tx.session.execute(
                    select(condition_rows.c.id, condition_rows.c.assignee_user_id)
                    .select_from(
                        condition_rows.join(records, records.c.id == condition_rows.c.record_id)
                    )
                    .where(
                        condition_rows.c.id == condition_id,
                        records.c.engagement_id == engagement_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if found is None:
            raise NotFound("acceptance_condition")
        if found["assignee_user_id"] != ctx.user_id:
            await _not_client_service(ctx, engagement_id)
        done = (
            await tx.session.execute(
                select(condition_events.c.id).where(
                    condition_events.c.condition_id == condition_id
                )
            )
        ).scalar_one_or_none()
        if done is not None:
            raise DomainInvalid(facts={"condition_id": str(condition_id)})
        event_id = uuid4()
        await tx.session.execute(
            insert(condition_events).values(
                id=event_id,
                tenant_id=ctx.tenant_id,
                condition_id=condition_id,
                note_sealed=(
                    await _seal(ctx.tenant, note, "acceptance_condition_event", event_id)
                    if note
                    else None
                ),
                actor_id=ctx.user_id,
            )
        )
        tx.record(
            "acceptance.condition_completed",
            target=Target("engagement", engagement_id),
            after=Ref(condition_id=condition_id),
        )
    record_view = await acceptance_record(ctx, engagement_id)
    return next(c for c in record_view.conditions if c.id == condition_id)


# --- the risk-partner review (AC-4) -------------------------------------------------------------


async def request_risk_review(
    ctx: AuthContext, engagement_id: UUID, partner_id: UUID
) -> RiskReview:
    """The EP names another partner (never an engagement partner here, never someone walled
    from the client, always a partner-level member): 422 `invalid` otherwise."""
    async with uow(ctx.tenant) as tx:
        ref, record = await _writable(tx, ctx, engagement_id, REQUEST_REVIEW)
        _open_record(record)
        facts = await member_facts(ctx.tenant, partner_id)
        standing = await team_standing(ctx.tenant, engagement_id, partner_id)
        if (
            partner_id == ctx.user_id
            or facts is None
            or facts.client
            or facts.level != "partner"
            or standing == "partner"
            or await hidden_clients(ctx.tenant, partner_id, [ref.client_id])
        ):
            raise DomainInvalid(facts={"field": "partner_id"})
        await tx.session.execute(
            insert(reviews).values(
                tenant_id=ctx.tenant_id,
                record_id=record["id"],
                event="requested",
                partner_id=partner_id,
                actor_id=ctx.user_id,
            )
        )
        await _bump(tx, record["id"])
        tx.record(
            "acceptance.review_requested",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=partner_id),
        )
        tx.emit(  # P-07-T47: the named partner is told (`risk_partner_review_requested`)
            AcceptanceReviewRequested(
                engagement_id=engagement_id,
                record_id=record["id"],
                partner_id=partner_id,
                by_user=ctx.user_id,
            )
        )
    async with tenant_session(ctx.tenant) as session:
        found = await _review(session, cast(UUID, record["id"]))
    if found is None:
        raise NotFound("risk_partner_review")
    return found


async def complete_risk_review(ctx: AuthContext, engagement_id: UUID) -> RiskReview:
    """Only the named risk partner completes the open review. Authorised on the client (the
    derived `firm_partner`, walls applied), since the risk partner is not on the team."""
    _live_human(ctx, COMPLETE_REVIEW)
    ref = await get_ref(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        await authorise(ctx, COMPLETE_REVIEW, Resource.client(ctx.tenant_id, ref.client_id))
        record = await _record_for_update(tx, engagement_id)
        _open_record(record)
        current = await _review(tx.session, cast(UUID, record["id"]))
        if current is None or current.partner_id != ctx.user_id:
            raise Forbidden(COMPLETE_REVIEW, "role")
        # DEC-375 note (re-review 1): independence holds at completion too; someone seated as
        # an engagement partner here since the request is no longer the risk partner.
        if await team_standing(ctx.tenant, engagement_id, ctx.user_id) == "partner":
            raise Forbidden(COMPLETE_REVIEW, "role")
        if current.completed_at is not None:
            raise DomainInvalid(facts={"record_id": str(record["id"])})
        await tx.session.execute(
            insert(reviews).values(
                tenant_id=ctx.tenant_id,
                record_id=record["id"],
                event="completed",
                partner_id=ctx.user_id,
                actor_id=ctx.user_id,
            )
        )
        await _bump(tx, record["id"])
        tx.record(
            "acceptance.review_completed",
            target=Target("engagement", engagement_id),
            after=Ref(record_id=record["id"]),
        )
    async with tenant_session(ctx.tenant) as session:
        found = await _review(session, cast(UUID, record["id"]))
    if found is None:
        raise NotFound("risk_partner_review")
    return found


# --- the decision (AC-6 to AC-10) ---------------------------------------------------------------


async def decide_acceptance(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    option: Option,
    rationale: str,
    conditions: Sequence[NewCondition],
    seen_version: int,
) -> RecordView:
    """The engagement partner's decision with fresh MFA (matrix), by a live person (here), on an
    Awaiting-partner record at `seen_version`; one insert-only row (`actor_kind = 'human'`
    CHECK), the record locked, the engagement Prospect → Accepted or Declined (INV-1)."""
    _live_human(ctx, DECIDE)
    # DEC-375 (M3): the decider is a partner-level member at decision time, whatever role an
    # engagement's team gave them; the database checks the same (0165).
    facts_of_decider = await member_facts(ctx.tenant, ctx.user_id)
    if facts_of_decider is None or facts_of_decider.client or facts_of_decider.level != "partner":
        raise Forbidden(DECIDE, "role")
    rationale = rationale.strip()
    async with uow(ctx.tenant) as tx:
        _, record = await _writable(tx, ctx, engagement_id, DECIDE)
        _open_record(record)
        record_id = cast(UUID, record["id"])
        if record["version"] != seen_version:
            raise AcceptanceStale(facts={"record_id": str(record_id)})
        if record["status"] != "awaiting_partner":
            raise AcceptanceNotReady(facts={"record_id": str(record_id)})
        if not rationale:
            raise RationaleRequired(facts={"field": "rationale"})
        if option == "accept_with_conditions" and not conditions:
            raise RationaleRequired(facts={"field": "conditions"})
        if option != "accept_with_conditions" and conditions:
            raise DomainInvalid(facts={"field": "conditions"})
        if any(not c.text.strip() for c in conditions):
            raise DomainInvalid(facts={"field": "conditions"})
        for c in conditions:
            facts = await member_facts(ctx.tenant, c.assignee_user_id)
            if facts is None or facts.client:
                raise DomainInvalid(facts={"field": "conditions"})
        review_now = await _review(tx.session, record_id)
        if (
            review_now is not None
            and review_now.completed_at is not None
            and (review_now.partner_id == ctx.user_id)
        ):  # DEC-375 note (re-review 1): the reviewer never decides what they reviewed
            raise Forbidden(DECIDE, "role")
        # DEC-375 (H1): a record ever rated High keeps needing the review.
        if record["risk_rating"] == "high" or record["high_risk_seen"]:
            review = await _review(tx.session, record_id)
            if review is None or review.completed_at is None:
                raise ReviewRequired(facts={"record_id": str(record_id)})
        if ctx.mfa_at is None:  # the matrix asked for it already; the row records when
            raise Forbidden(DECIDE, "condition")
        decision_id = uuid4()
        await tx.session.execute(
            insert(decisions).values(
                id=decision_id,
                tenant_id=ctx.tenant_id,
                record_id=record_id,
                option=option,
                rationale_sealed=await _seal(
                    ctx.tenant, rationale, "acceptance_decision", decision_id
                ),
                decided_by=ctx.user_id,
                mfa_verified_at=ctx.mfa_at,
            )
        )
        for position, c in enumerate(conditions, start=1):
            condition_id = uuid4()
            await tx.session.execute(
                insert(condition_rows).values(
                    id=condition_id,
                    tenant_id=ctx.tenant_id,
                    record_id=record_id,
                    decision_id=decision_id,
                    position=position,
                    text_sealed=await _seal(
                        ctx.tenant, c.text.strip(), "acceptance_condition.text", condition_id
                    ),
                    assignee_user_id=c.assignee_user_id,
                    due_on=c.due_on,
                )
            )
        accepted = option != "decline"
        await _bump(tx, record_id, status="decided" if accepted else "declined")
        status = (
            await tx.session.execute(
                select(Engagement.status).where(Engagement.id == engagement_id)
            )
        ).scalar_one()
        if status == "prospect":
            await transition(tx, engagement_id, "accepted" if accepted else "declined", by=ctx)
        elif not accepted:
            raise IllegalTransition(facts={"from_status": status, "to_status": "declined"})
        tx.record(
            "acceptance.decided",
            target=Target("engagement", engagement_id),
            after=Ref(record_id=record_id, decision_id=decision_id, conditions=len(conditions)),
        )
        tx.emit(AcceptanceDecided(engagement_id=engagement_id, record_id=record_id, option=option))
        if accepted:
            tx.emit(GateMet(engagement_id=engagement_id, gate="G1"))
    return await acceptance_record(ctx, engagement_id)


# --- opening a record ("Start acceptance", intake) ----------------------------------------------


async def open_record(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    engagement_id: UUID,
    client_id: UUID,
    family: str,
    prior_engagement_id: UUID | None,
    kind: Kind | None = None,
) -> UUID:
    """A Draft record for a new Prospect engagement, pinned to the newest version of the firm's
    questionnaire for the type's family; inside the caller's unit of work (after its
    authorisation). 409 `acceptance_template_missing` when the firm has none. `kind` when the
    caller knows it (the intake: an entity added under an existing client, P-07-T42)."""
    version = (
        await tx.session.execute(
            select(template_versions.c.id)
            .select_from(
                template_versions.join(
                    templates, templates.c.id == template_versions.c.template_id
                )
            )
            .where(templates.c.family == family)
            .order_by(
                template_versions.c.created_at.desc(),
                template_versions.c.version_no.desc(),
                template_versions.c.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if version is None:
        raise AcceptanceTemplateMissing(facts={"family": family})
    prior_record: UUID | None = None
    if prior_engagement_id is not None:
        prior_record = (
            await tx.session.execute(
                select(records.c.id).where(records.c.engagement_id == prior_engagement_id)
            )
        ).scalar_one_or_none()
        kind = "continuance"
    elif kind is None:
        others = (
            await tx.session.execute(
                select(Engagement.id)
                .where(
                    Engagement.client_id == client_id,
                    Engagement.id != engagement_id,
                    Engagement.status != "declined",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        kind = "new_engagement_existing_client" if others is not None else "new_client"
    record_id = uuid4()
    await tx.session.execute(
        insert(records).values(
            id=record_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            client_id=client_id,
            kind=kind,
            template_version_id=version,
            prepared_by=ctx.user_id,
            prior_record_id=prior_record,
        )
    )
    tx.record(
        "acceptance.record_opened",
        target=Target("engagement", engagement_id),
        after=Ref(record_id=record_id),
    )
    return record_id


async def record_id_of(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return (
            await session.execute(
                select(records.c.id).where(records.c.engagement_id == engagement_id)
            )
        ).scalar_one_or_none()
