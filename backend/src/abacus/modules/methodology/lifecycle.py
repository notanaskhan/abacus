"""A methodology version's lifecycle, live (K-01-T06; K-01 §3.2; `methodology-programs.md`;
DEC-651).

- **Submit** (`methodology.manage`): Draft to Needs review, at the `row_version` the person saw
  (409 `stale_version`); any other status is 409 `version_frozen`. It notifies the firm's
  quality partners (`methodology.review_requested`).
- **Checklist**, computed by code from the version's own rows: it has programs, it has steps, and
  every program has a step. Its hash (`sha256:`) is what the approver saw; a different hash at
  approval is 409 `checklist_changed`, an unmet item 409 `checklist_unmet`.
- **Approve** (`methodology.approve`: a quality partner, fresh MFA; human-only, INV-1): Needs
  review to Published from `effective_from`, the person recorded as approver (0180's trigger binds
  them to the session's person). The template's published versions are superseded the day before
  (`effective_to`), and the default for new engagements moves to the new version when one of
  them held it or none did. Each superseded version emits `methodology_version.superseded`. An
  agent, the system or support asking is refused and audited (`decision.refused_non_human`); a
  person without the action is refused and audited (`methodology_version.approve_refused`), each
  in its own unit of work so the refusal is kept. K-01-T18: an open parse flag is 409
  `flags_open`, an unverified source on a step no person has confirmed 409 `unverified_sources`.
- **Effective on a date** (`version_effective_on`): the template's published or superseded
  version whose dates cover the day, for the engagement's pin at its acceptance date.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import Insert, func, insert, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of
from abacus.modules.methodology.events import (
    MethodologyReviewRequested,
    MethodologyVersionSuperseded,
)
from abacus.modules.methodology.models import (
    MethodologyVersion,
    MethodologyVersionEvent,
    MethodologyVersionState,
    Program,
    ProgramStep,
    ProgramStepSource,
)

MANAGE: Final = "methodology.manage"
APPROVE: Final = "methodology.approve"
SUBJECT: Final = "methodology_version"


class VersionStale(DomainConflict):
    """The version changed since you read it: reload."""

    code = "stale_version"


class VersionFrozen(DomainConflict):
    """The version is not in a status this step takes (a draft is submitted; a version in
    review is approved)."""

    code = "version_frozen"


class ChecklistChanged(DomainConflict):
    """The checklist is not the one you approved: review it again."""

    code = "checklist_changed"


class ChecklistUnmet(DomainConflict):
    """An approval checklist item is not met (`facts.item`)."""

    code = "checklist_unmet"


class FlagsOpen(DomainConflict):
    """A parse flag on a step is not resolved yet (K-01-T18, AC3.4): confirm or edit it."""

    code = "flags_open"


class UnverifiedSources(DomainConflict):
    """A step's source quote was not found on its cited page and no person has confirmed or
    edited the step (K-01-T18, AC3.4, AC7.5)."""

    code = "unverified_sources"


class EffectiveTooEarly(DomainInvalid):
    """A version takes effect after the one it supersedes began."""

    code = "effective_from_too_early"


@dataclass(frozen=True)
class ChecklistItem:
    code: str
    ok: bool
    n: int


@dataclass(frozen=True)
class VersionState:
    version_id: UUID
    template_id: UUID
    label: str
    status: str
    effective_from: date | None
    effective_to: date | None
    approved_by: UUID | None
    approved_by_name: str | None
    approved_at: datetime | None
    approval_basis: str | None
    standards_set_id: UUID | None
    engagement_types: list[str]
    default_for_new_engagements: bool
    drafted_from_version_id: UUID | None
    row_version: int
    checklist: list[ChecklistItem]
    checklist_hash: str
    # K-01-T18 (KNW-02 d): the QM reference and the mapped set's code and label.
    quality_management_ref: str | None = None
    standards_set_code: str | None = None
    standards_set_label: str | None = None


async def checklist_of(session: AsyncSession, version_id: UUID) -> list[ChecklistItem]:
    programs = list(
        (await session.execute(select(Program.id).where(Program.version_id == version_id)))
        .scalars()
        .all()
    )
    per_program = dict(
        (
            await session.execute(
                select(ProgramStep.program_id, func.count())
                .where(ProgramStep.program_id.in_(programs))
                .group_by(ProgramStep.program_id)
            )
        )
        .tuples()
        .all()
    )
    steps = sum(per_program.values())
    empty = sum(1 for p in programs if not per_program.get(p))
    return [
        ChecklistItem("has_programs", bool(programs), len(programs)),
        ChecklistItem("has_steps", steps > 0, steps),
        ChecklistItem("every_program_has_steps", empty == 0, empty),
    ]


def _day(on: date) -> int:
    """A date as an audit ref (integers only): 2026-01-01 is 20260101."""
    return on.year * 10000 + on.month * 100 + on.day


def hash_of(items: list[ChecklistItem]) -> str:
    body = json.dumps(
        [[i.code, i.ok, i.n] for i in items], separators=(",", ":"), sort_keys=True
    ).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


async def _state_row(
    session: AsyncSession, version_id: UUID, *, lock: bool = False
) -> tuple[MethodologyVersionState, MethodologyVersion]:
    stmt = (
        select(MethodologyVersionState, MethodologyVersion)
        .join(MethodologyVersion, MethodologyVersion.id == MethodologyVersionState.version_id)
        .where(MethodologyVersionState.version_id == version_id)
    )
    if lock:
        stmt = stmt.with_for_update(of=MethodologyVersionState)
    found = (await session.execute(stmt)).tuples().one_or_none()
    if found is None:
        raise NotFound(SUBJECT)
    return found


async def _view(session: AsyncSession, version_id: UUID) -> VersionState:
    state, version = await _state_row(session, version_id)
    items = await checklist_of(session, version_id)
    names = await names_of([state.approved_by]) if state.approved_by else {}
    return VersionState(
        version_id=state.version_id,
        template_id=state.template_id,
        label=version.label,
        status=state.status,
        effective_from=state.effective_from,
        effective_to=state.effective_to,
        approved_by=state.approved_by,
        approved_by_name=names.get(state.approved_by) if state.approved_by else None,
        approved_at=state.approved_at,
        approval_basis=state.approval_basis,
        standards_set_id=state.standards_set_id,
        engagement_types=list(state.engagement_types),
        default_for_new_engagements=state.default_for_new_engagements,
        drafted_from_version_id=version.drafted_from_version_id,
        row_version=state.row_version,
        checklist=items,
        checklist_hash=hash_of(items),
        quality_management_ref=state.quality_management_ref,
        **await _standards_set(session, state.standards_set_id),
    )


async def _standards_set(session: AsyncSession, set_id: UUID | None) -> dict[str, str | None]:
    """The mapped set's code and label (0580's reader: platform rows, by id)."""
    if set_id is None:
        return {"standards_set_code": None, "standards_set_label": None}
    found = (
        await session.execute(
            text("SELECT code, label FROM standards_set_named(:id)"), {"id": set_id}
        )
    ).one_or_none()
    return {
        "standards_set_code": None if found is None else str(found[0]),
        "standards_set_label": None if found is None else str(found[1]),
    }


async def view_in(session: AsyncSession, version_id: UUID) -> VersionState:
    """A version's state inside the caller's session (K-01-T14's drafts)."""
    return await _view(session, version_id)


async def version_state(ctx: AuthContext, version_id: UUID) -> VersionState:
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        return await _view(session, version_id)


def _event(ctx: AuthContext, version_id: UUID, kind: str, facts: dict[str, object]) -> Insert:
    return insert(MethodologyVersionEvent).values(
        tenant_id=ctx.tenant_id,
        version_id=version_id,
        kind=kind,
        actor_user_id=ctx.user_id,
        facts=facts,
    )


async def submit_version(ctx: AuthContext, version_id: UUID, row_version: int) -> VersionState:
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(MANAGE, "role")
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        state, _version = await _state_row(tx.session, version_id, lock=True)
        if state.row_version != row_version:
            raise VersionStale(facts={"version_id": str(version_id)})
        if state.status != "draft":
            raise VersionFrozen(facts={"status": state.status})
        await tx.session.execute(
            update(MethodologyVersionState)
            .where(MethodologyVersionState.version_id == version_id)
            .values(status="needs_review", row_version=state.row_version + 1)
        )
        await tx.session.execute(_event(ctx, version_id, "submitted", {}))
        tx.record("methodology_version.submitted", target=Target(SUBJECT, version_id))
        tx.emit(
            MethodologyReviewRequested(
                version_id=version_id, template_id=state.template_id, by_user=ctx.user_id
            )
        )
        return await _view(tx.session, version_id)


async def record_refusal(ctx: AuthContext, version_id: UUID, action: str) -> None:
    """Keep the refusal: its own unit of work, so the raise that follows rolls nothing back. A
    non-human's attempt is recorded by the system for the person it ran for (an agent's audit
    row must name its person; the database's check)."""
    tenant = (
        ctx.tenant
        if ctx.tenant.actor_kind == "human"
        else TenantContext(
            ctx.tenant_id,
            "system",
            f"methodology:refusal:{version_id}",
            on_behalf_of_user_id=ctx.tenant.on_behalf_of_user_id or ctx.user_id,
        )
    )
    async with uow(tenant) as tx:
        tx.record(action, target=Target(SUBJECT, version_id), after=Ref(version=version_id))


async def approve_guard(ctx: AuthContext, version_id: UUID) -> None:
    """INV-1 at the service: a client principal is 404; an agent, the system or support is
    refused and audited (`decision.refused_non_human`); a person without the action is refused
    and audited (`methodology_version.approve_refused`)."""
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        await record_refusal(ctx, version_id, "decision.refused_non_human")
        raise Forbidden(APPROVE, "role")
    try:
        await authorise(ctx, APPROVE, Resource.firm(ctx.tenant_id))
    except Forbidden:
        await record_refusal(ctx, version_id, "methodology_version.approve_refused")
        raise


async def review_guard(session: AsyncSession, version_id: UUID) -> None:
    """K-01-T18 (AC3.4): nothing is approvable while a parse flag is open, or while a step's
    source quote is unverified and no person has confirmed or edited that step."""
    open_flags = (
        await session.execute(
            select(func.count())
            .select_from(ProgramStep)
            .where(
                ProgramStep.version_id == version_id,
                ProgramStep.parse_flag.is_not(None),
                ProgramStep.flag_resolution.is_(None),
            )
        )
    ).scalar_one()
    if open_flags:
        raise FlagsOpen(facts={"version_id": str(version_id), "count": int(open_flags)})
    unverified = (
        await session.execute(
            select(func.count())
            .select_from(ProgramStepSource)
            .join(ProgramStep, ProgramStep.id == ProgramStepSource.step_id)
            .where(
                ProgramStep.version_id == version_id,
                ProgramStepSource.verified.is_(False),
                ProgramStep.flag_resolution.is_(None),
            )
        )
    ).scalar_one()
    if unverified:
        raise UnverifiedSources(facts={"version_id": str(version_id), "count": int(unverified)})


async def approve_version(
    ctx: AuthContext,
    version_id: UUID,
    *,
    effective_from: date,
    checklist_hash: str,
    row_version: int,
) -> VersionState:
    await approve_guard(ctx, version_id)
    async with uow(ctx.tenant) as tx:
        state, _version = await _state_row(tx.session, version_id, lock=True)
        if state.row_version != row_version:
            raise VersionStale(facts={"version_id": str(version_id)})
        if state.status != "needs_review":
            raise VersionFrozen(facts={"status": state.status})
        await review_guard(tx.session, version_id)
        items = await checklist_of(tx.session, version_id)
        if hash_of(items) != checklist_hash:
            raise ChecklistChanged(facts={"version_id": str(version_id)})
        unmet = next((i for i in items if not i.ok), None)
        if unmet is not None:
            raise ChecklistUnmet(facts={"item": unmet.code})
        prior = list(
            (
                await tx.session.execute(
                    select(MethodologyVersionState)
                    .where(
                        MethodologyVersionState.template_id == state.template_id,
                        MethodologyVersionState.status == "published",
                        MethodologyVersionState.version_id != version_id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        ends = effective_from - timedelta(days=1)
        if any(p.effective_from is not None and p.effective_from > ends for p in prior):
            raise EffectiveTooEarly(facts={"field": "effective_from"})
        held_default = any(p.default_for_new_engagements for p in prior)
        for p in prior:
            await tx.session.execute(
                update(MethodologyVersionState)
                .where(MethodologyVersionState.version_id == p.version_id)
                .values(
                    status="superseded",
                    effective_to=ends,
                    default_for_new_engagements=False,
                    row_version=p.row_version + 1,
                )
            )
            await tx.session.execute(
                _event(ctx, p.version_id, "superseded", {"by_version_id": str(version_id)})
            )
            tx.record(
                "methodology_version.superseded",
                target=Target(SUBJECT, p.version_id),
                after=Ref(by=version_id, effective_to=_day(ends)),
            )
            tx.emit(
                MethodologyVersionSuperseded(
                    version_id=p.version_id, template_id=p.template_id, by_version_id=version_id
                )
            )
        await tx.session.execute(
            update(MethodologyVersionState)
            .where(MethodologyVersionState.version_id == version_id)
            .values(
                status="published",
                effective_from=effective_from,
                effective_to=None,
                approved_by=ctx.user_id,
                approved_at=func.abacus_now(),
                approved_actor_kind="human",
                approval_basis="approved",
                default_for_new_engagements=held_default or not prior,
                row_version=state.row_version + 1,
            )
        )
        await tx.session.execute(
            _event(ctx, version_id, "approved", {"effective_from": effective_from.isoformat()})
        )
        tx.record(
            "methodology_version.approved",
            target=Target(SUBJECT, version_id),
            after=Ref(effective_from=_day(effective_from), superseded=len(prior)),
        )
        return await _view(tx.session, version_id)


async def version_effective_on(session: AsyncSession, template_id: UUID, on: date) -> UUID | None:
    """The template's version in force on `on` (published or superseded, dates covering it)."""
    return (
        await session.execute(
            select(MethodologyVersionState.version_id)
            .where(
                MethodologyVersionState.template_id == template_id,
                MethodologyVersionState.status.in_(("published", "superseded")),
                MethodologyVersionState.effective_from <= on,
                or_(
                    MethodologyVersionState.effective_to.is_(None),
                    MethodologyVersionState.effective_to >= on,
                ),
            )
            .order_by(MethodologyVersionState.effective_from.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


__all__ = [
    "ChecklistItem",
    "VersionState",
    "approve_guard",
    "approve_version",
    "checklist_of",
    "hash_of",
    "record_refusal",
    "submit_version",
    "version_effective_on",
    "version_state",
    "view_in",
]
