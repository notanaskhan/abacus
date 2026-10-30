"""Drafts and mandatory locks (K-01-T14; K-01 §3.5 AC5.1 to AC5.4, AC5.7; KNW-03 c, d; DEC-1361).

- **A draft** (`methodology.manage`, a person): vN+1 copied from a published version, with
  `drafted_from_version_id` and every row carried over: areas, request items, account rules,
  programs, steps (each keeps its `step_key`, so an anchor survives the draft) and their PBC
  links. One open draft per template (409 `draft_exists`); the number is consumed even when the
  draft is discarded (versions are insert-only, AC5.7).
- **Step edits** in a draft only (0224's frozen trigger refuses any other status; the service
  answers 409 `version_frozen` first): edit text, assertions, standards, level and guidance;
  add a step (origin `manual`, a fresh key); remove a step. A mandatory step is locked for all
  three (409 `mandatory_locked`); a step a PBC request links to stays (409 `step_has_requests`).
  Every write carries the `row_version` the person saw (`If-Match`; 409 `stale_version`). An
  edit keeps the step's key and origin, so its citation and source stay; `edited_by` names the
  person.
- **The mandatory lock** (`methodology.approve`: the QM owner with fresh MFA; INV-1): a person's
  act only. The agent, the system and support are refused and audited
  (`decision.refused_non_human`), a person without the action is refused and audited
  (`methodology_step.mandatory_refused`), and 0464's trigger refuses a non-person at the database.
- **The change list** (`draft_changes`): computed by code against `drafted_from` by step key:
  added, changed (which fields), removed and unchanged; numbering alone is not a change.
- **Discard** (`methodology.manage`): a draft or a version in review becomes `discarded`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.methodology.lifecycle import (
    APPROVE,
    MANAGE,
    SUBJECT,
    VersionFrozen,
    VersionStale,
    VersionState,
    record_refusal,
    view_in,
)
from abacus.modules.methodology.models import (
    MethodologyAccountRule,
    MethodologyArea,
    MethodologyRequestItem,
    MethodologyTemplate,
    MethodologyVersion,
    MethodologyVersionEvent,
    MethodologyVersionState,
    Program,
    ProgramStep,
    ProgramStepPbcLink,
)
from abacus.modules.methodology.programs import StepView
from abacus.modules.methodology.repository import lock_template

STEP: Final = "methodology_step"
_OPEN: Final = ("draft", "parsing", "needs_review")
# What an edit may change; the rest of a step (its key, origin, lock) is carried as it is.
EDITABLE: Final = ("text", "assertions", "standard_refs", "level", "guidance")
# What the change list compares (numbering is not a change; a lock change is).
COMPARED: Final = (*EDITABLE, "mandatory", "lock_note")


class NotPublished(DomainConflict):
    """A draft starts from a published version."""

    code = "version_not_published"


class DraftExists(DomainConflict):
    """The template already has a draft or a version in review."""

    code = "draft_exists"


class MandatoryLocked(DomainConflict):
    """Only the QM owner can remove or unlock mandatory steps."""

    code = "mandatory_locked"


class StepHasRequests(DomainConflict):
    """A step a PBC request links to stays in the program."""

    code = "step_has_requests"


@dataclass(frozen=True)
class StepChange:
    step_key: str
    change: str  # added · changed · removed
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class DraftChanges:
    version_id: UUID
    against_version_id: UUID | None
    changes: tuple[StepChange, ...]
    unchanged: int


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _record(
    tx: UnitOfWork, ctx: AuthContext, version_id: UUID, kind: str, facts: dict[str, object]
) -> None:
    await tx.session.execute(
        insert(MethodologyVersionEvent).values(
            tenant_id=ctx.tenant_id,
            version_id=version_id,
            kind=kind,
            actor_user_id=ctx.user_id,
            facts=facts,
        )
    )


async def _state(session: AsyncSession, version_id: UUID) -> MethodologyVersionState:
    found = (
        await session.execute(
            select(MethodologyVersionState)
            .where(MethodologyVersionState.version_id == version_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if found is None:
        raise NotFound(SUBJECT)
    return found


async def _draft(session: AsyncSession, version_id: UUID) -> MethodologyVersionState:
    state = await _state(session, version_id)
    if state.status != "draft":
        raise VersionFrozen(facts={"status": state.status})
    return state


async def _step(
    session: AsyncSession, version_id: UUID, step_id: UUID, row_version: int | None
) -> ProgramStep:
    found = (
        await session.execute(
            select(ProgramStep)
            .where(ProgramStep.id == step_id, ProgramStep.version_id == version_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if found is None:
        raise NotFound(STEP)
    if row_version is not None and found.row_version != row_version:
        raise VersionStale(facts={"step_id": str(step_id)})
    return found


async def _view(session: AsyncSession, step_id: UUID) -> StepView:
    step = (
        await session.execute(select(ProgramStep).where(ProgramStep.id == step_id))
    ).scalar_one()
    number = (
        await session.execute(
            select(MethodologyVersion.version).where(MethodologyVersion.id == step.version_id)
        )
    ).scalar_one()
    links = (
        await session.execute(
            select(ProgramStepPbcLink.request_position)
            .where(ProgramStepPbcLink.step_id == step_id)
            .order_by(ProgramStepPbcLink.request_position)
        )
    ).scalars()
    return StepView(step, number, tuple(links))


# --- a draft ------------------------------------------------------------------------------------


async def _copy_rows(session: AsyncSession, source_id: UUID, draft_id: UUID) -> int:
    """Every row of the source version under the draft; returns the step count."""
    tenant = {"version_id": draft_id}
    areas = (
        await session.execute(
            select(MethodologyArea).where(MethodologyArea.version_id == source_id)
        )
    ).scalars()
    rows = [
        {
            **tenant,
            "tenant_id": a.tenant_id,
            "code": a.code,
            "name": a.name,
            "position": a.position,
        }
        for a in areas
    ]
    if rows:
        await session.execute(insert(MethodologyArea), rows)
    items = (
        await session.execute(
            select(MethodologyRequestItem).where(MethodologyRequestItem.version_id == source_id)
        )
    ).scalars()
    rows = [
        {
            **tenant,
            "tenant_id": t.tenant_id,
            "position": t.position,
            "area_code": t.area_code,
            "description": t.description,
            "retrievability_tier": t.retrievability_tier,
            "why": t.why,
            "good_looks_like": t.good_looks_like,
            "blocks_fieldwork": t.blocks_fieldwork,
            "effort": t.effort,
            "guidance_source": t.guidance_source,
            "guidance_approved_by": t.guidance_approved_by,
        }
        for t in items
    ]
    if rows:
        await session.execute(insert(MethodologyRequestItem), rows)
    rules = (
        await session.execute(
            select(MethodologyAccountRule).where(MethodologyAccountRule.version_id == source_id)
        )
    ).scalars()
    rows = [
        {
            **tenant,
            "tenant_id": r.tenant_id,
            "position": r.position,
            "area_code": r.area_code,
            "account_from": r.account_from,
            "account_to": r.account_to,
        }
        for r in rules
    ]
    if rows:
        await session.execute(insert(MethodologyAccountRule), rows)
    program_ids: dict[UUID, UUID] = {}
    for p in (
        await session.execute(
            select(Program).where(Program.version_id == source_id).order_by(Program.position)
        )
    ).scalars():
        program_ids[p.id] = (
            await session.execute(
                insert(Program)
                .values(
                    tenant_id=p.tenant_id,
                    version_id=draft_id,
                    code=p.code,
                    name=p.name,
                    position=p.position,
                    publisher_program_id=p.publisher_program_id,
                )
                .returning(Program.id)
            )
        ).scalar_one()
    step_ids: dict[UUID, UUID] = {}
    step_rows: list[dict[str, object]] = []
    for s in (
        await session.execute(select(ProgramStep).where(ProgramStep.version_id == source_id))
    ).scalars():
        step_ids[s.id] = uuid4()
        step_rows.append(
            {
                **tenant,
                "id": step_ids[s.id],
                "tenant_id": s.tenant_id,
                "program_id": program_ids[s.program_id],
                "step_key": s.step_key,
                "number": s.number,
                "text": s.text,
                "assertions": s.assertions,
                "standard_refs": s.standard_refs,
                "level": s.level,
                "mandatory": s.mandatory,
                "lock_note": s.lock_note,
                "guidance": s.guidance,
                "prepopulates": s.prepopulates,
                "depends_on_step_keys": s.depends_on_step_keys,
                "publisher_step_id": s.publisher_step_id,
                "origin": s.origin,
                "proposed_by_run_id": s.proposed_by_run_id,
                # A published version's flags are resolved; the draft starts clean of them.
                "parse_flag": None,
            }
        )
    if step_rows:
        await session.execute(insert(ProgramStep), step_rows)
    links = [
        {
            **tenant,
            "tenant_id": link.tenant_id,
            "step_id": step_ids[link.step_id],
            "request_position": link.request_position,
        }
        for link in (
            await session.execute(
                select(ProgramStepPbcLink).where(ProgramStepPbcLink.version_id == source_id)
            )
        ).scalars()
    ]
    if links:
        await session.execute(insert(ProgramStepPbcLink), links)
    return len(step_rows)


async def create_draft(ctx: AuthContext, version_id: UUID) -> VersionState:
    """KNW-03 c: Draft vN+1 from a published version (AC5.1)."""
    _person(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        source = (
            await tx.session.execute(
                select(MethodologyVersion).where(MethodologyVersion.id == version_id)
            )
        ).scalar_one_or_none()
        if source is None:
            raise NotFound(SUBJECT)
        latest = await lock_template(tx.session, source.template_id)
        state = await _state(tx.session, version_id)
        if state.status != "published":
            raise NotPublished(facts={"status": state.status})
        open_draft = await tx.session.scalar(
            select(func.count())
            .select_from(MethodologyVersionState)
            .where(
                MethodologyVersionState.template_id == source.template_id,
                MethodologyVersionState.status.in_(_OPEN),
            )
        )
        if open_draft:
            raise DraftExists(facts={"template_id": str(source.template_id)})
        number = latest + 1
        draft_id = uuid4()
        await tx.session.execute(
            insert(MethodologyVersion).values(
                id=draft_id,
                tenant_id=ctx.tenant_id,
                template_id=source.template_id,
                version=number,
                # A draft has no source file: its fingerprint is its lineage's (64 hex).
                source_fingerprint=hashlib.sha256(f"draft:{version_id}".encode()).hexdigest(),
                imported_by=ctx.user_id,
                label=f"v{number}",
                origin="draft",
                drafted_from_version_id=version_id,
            )
        )
        steps = await _copy_rows(tx.session, version_id, draft_id)
        types = (
            await tx.session.execute(
                select(MethodologyTemplate.engagement_types).where(
                    MethodologyTemplate.id == source.template_id
                )
            )
        ).scalar_one()
        await tx.session.execute(
            insert(MethodologyVersionState).values(
                tenant_id=ctx.tenant_id,
                version_id=draft_id,
                template_id=source.template_id,
                status="draft",
                engagement_types=list(types),
                default_for_new_engagements=False,
                row_version=1,
            )
        )
        await _record(tx, ctx, draft_id, "draft_created", {"from_version_id": str(version_id)})
        tx.record(
            "methodology_version.draft_created",
            target=Target(SUBJECT, draft_id),
            after=Ref(from_version_id=version_id, version=number, steps=steps),
        )
        return await view_in(tx.session, draft_id)


async def discard_draft(ctx: AuthContext, version_id: UUID, row_version: int) -> VersionState:
    """A draft (or a version in review) is discarded; its number stays consumed (AC5.7)."""
    _person(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        state = await _state(tx.session, version_id)
        if state.row_version != row_version:
            raise VersionStale(facts={"version_id": str(version_id)})
        if state.status not in ("draft", "needs_review"):
            raise VersionFrozen(facts={"status": state.status})
        await tx.session.execute(
            update(MethodologyVersionState)
            .where(MethodologyVersionState.version_id == version_id)
            .values(status="discarded", row_version=state.row_version + 1)
        )
        await _record(tx, ctx, version_id, "discarded", {"from_status": state.status})
        tx.record("methodology_version.discarded", target=Target(SUBJECT, version_id))
        return await view_in(tx.session, version_id)


# --- steps in a draft ---------------------------------------------------------------------------


async def _bump(session: AsyncSession, version_id: UUID) -> None:
    """A draft's content changed: its state row moves (a reader sees the draft is newer)."""
    await session.execute(
        update(MethodologyVersionState)
        .where(MethodologyVersionState.version_id == version_id)
        .values(row_version=MethodologyVersionState.row_version + 1)
    )


async def _defer_numbers(session: AsyncSession) -> None:
    await session.execute(text("SET CONSTRAINTS program_steps_one_number DEFERRED"))


async def edit_step(
    ctx: AuthContext,
    version_id: UUID,
    step_id: UUID,
    changes: dict[str, object],
    row_version: int,
) -> StepView:
    """KNW-03 c, AC5.2: an optional step's content; the key, origin and lock are carried."""
    _person(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise ValueError(f"not editable: {', '.join(unknown)}")
    async with uow(ctx.tenant) as tx:
        await _draft(tx.session, version_id)
        step = await _step(tx.session, version_id, step_id, row_version)
        if step.mandatory:
            raise MandatoryLocked(facts={"step_id": str(step_id)})
        moved = [k for k, v in changes.items() if getattr(step, k) != v]
        if moved:
            await tx.session.execute(
                update(ProgramStep)
                .where(ProgramStep.id == step_id)
                .values(
                    **{k: changes[k] for k in moved},
                    edited_by=ctx.user_id,
                    edited_at=func.abacus_now(),
                    row_version=step.row_version + 1,
                )
            )
            await _bump(tx.session, version_id)
            await _record(
                tx, ctx, version_id, "step_edited", {"step_key": step.step_key, "fields": moved}
            )
            tx.record(
                "methodology_step.edited",
                target=Target(STEP, step_id),
                after=Ref(version_id=version_id, fields=len(moved)),
            )
        return await _view(tx.session, step_id)


def _new_key(program_code: str) -> str:
    base = re.sub(r"[^a-z0-9_.-]", "-", program_code.casefold()).strip("-") or "step"
    return f"{base[:60]}-m{uuid4().hex[:12]}"


async def add_step(
    ctx: AuthContext,
    version_id: UUID,
    program_id: UUID,
    *,
    text_: str,
    assertions: Sequence[str],
    standard_refs: Sequence[str],
    level: str,
    after_step_id: UUID | None,
) -> StepView:
    """KNW-03 c, + Step: appended, or after `after_step_id` with the steps below renumbered."""
    _person(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await _draft(tx.session, version_id)
        program = (
            await tx.session.execute(
                select(Program).where(Program.id == program_id, Program.version_id == version_id)
            )
        ).scalar_one_or_none()
        if program is None:
            raise NotFound("program")
        steps = list(
            (
                await tx.session.execute(
                    select(ProgramStep)
                    .where(ProgramStep.program_id == program_id)
                    .order_by(ProgramStep.number)
                    .with_for_update()
                )
            ).scalars()
        )
        number = (steps[-1].number if steps else 0) + 1
        if after_step_id is not None:
            after = next((s for s in steps if s.id == after_step_id), None)
            if after is None:
                raise NotFound(STEP)
            number = after.number + 1
            below = [s for s in steps if s.number >= number]
            if below:
                await _defer_numbers(tx.session)
                for s in below:
                    await tx.session.execute(
                        update(ProgramStep)
                        .where(ProgramStep.id == s.id)
                        .values(number=s.number + 1, row_version=s.row_version + 1)
                    )
        step_id = uuid4()
        key = _new_key(program.code)
        await tx.session.execute(
            insert(ProgramStep).values(
                id=step_id,
                tenant_id=ctx.tenant_id,
                version_id=version_id,
                program_id=program_id,
                step_key=key,
                number=number,
                text=text_,
                assertions=list(assertions),
                standard_refs=list(standard_refs),
                level=level,
                mandatory=False,
                origin="manual",
            )
        )
        await _bump(tx.session, version_id)
        await _record(tx, ctx, version_id, "step_added", {"step_key": key, "number": number})
        tx.record(
            "methodology_step.added",
            target=Target(STEP, step_id),
            after=Ref(version_id=version_id, program_id=program_id, number=number),
        )
        return await _view(tx.session, step_id)


async def remove_step(ctx: AuthContext, version_id: UUID, step_id: UUID, row_version: int) -> UUID:
    """KNW-03 c: an optional, unlinked step leaves the draft; the steps below move up."""
    _person(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await _draft(tx.session, version_id)
        step = await _step(tx.session, version_id, step_id, row_version)
        if step.mandatory:
            raise MandatoryLocked(facts={"step_id": str(step_id)})
        linked = await tx.session.scalar(
            select(func.count())
            .select_from(ProgramStepPbcLink)
            .where(ProgramStepPbcLink.step_id == step_id)
        )
        if linked:
            raise StepHasRequests(facts={"step_id": str(step_id)})
        await tx.session.execute(delete(ProgramStep).where(ProgramStep.id == step_id))
        below = list(
            (
                await tx.session.execute(
                    select(ProgramStep)
                    .where(
                        ProgramStep.program_id == step.program_id,
                        ProgramStep.number > step.number,
                    )
                    .order_by(ProgramStep.number)
                    .with_for_update()
                )
            ).scalars()
        )
        if below:
            await _defer_numbers(tx.session)
            for s in below:
                await tx.session.execute(
                    update(ProgramStep)
                    .where(ProgramStep.id == s.id)
                    .values(number=s.number - 1, row_version=s.row_version + 1)
                )
        await _bump(tx.session, version_id)
        await _record(tx, ctx, version_id, "step_removed", {"step_key": step.step_key})
        tx.record(
            "methodology_step.removed",
            target=Target(STEP, step_id),
            after=Ref(version_id=version_id, number=step.number),
        )
    return step_id


async def mandatory_guard(ctx: AuthContext, version_id: UUID) -> None:
    """INV-1 at the service (AC5.3), before the flag is read: refusals are kept."""
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        await record_refusal(ctx, version_id, "decision.refused_non_human")
        raise Forbidden(APPROVE, "role")
    try:
        await authorise(ctx, APPROVE, Resource.firm(ctx.tenant_id))
    except Forbidden:
        await record_refusal(ctx, version_id, "methodology_step.mandatory_refused")
        raise


async def set_mandatory(
    ctx: AuthContext,
    version_id: UUID,
    step_id: UUID,
    *,
    mandatory: bool,
    lock_note: str | None,
    row_version: int,
) -> StepView:
    """KNW-03 d: the QM owner locks or unlocks a draft step (a person, fresh MFA)."""
    await mandatory_guard(ctx, version_id)
    note = lock_note.strip() if mandatory and lock_note and lock_note.strip() else None
    async with uow(ctx.tenant) as tx:
        await _draft(tx.session, version_id)
        step = await _step(tx.session, version_id, step_id, row_version)
        if step.mandatory != mandatory or step.lock_note != note:
            await tx.session.execute(
                update(ProgramStep)
                .where(ProgramStep.id == step_id)
                .values(
                    mandatory=mandatory,
                    lock_note=note,
                    edited_by=ctx.user_id,
                    edited_at=func.abacus_now(),
                    row_version=step.row_version + 1,
                )
            )
            await _bump(tx.session, version_id)
            await _record(
                tx,
                ctx,
                version_id,
                "mandatory_changed",
                {"step_key": step.step_key, "mandatory": mandatory},
            )
            tx.record(
                "methodology_step.mandatory_changed",
                target=Target(STEP, step_id),
                after=Ref(version_id=version_id, mandatory=int(mandatory)),
            )
        return await _view(tx.session, step_id)


# --- the change list ----------------------------------------------------------------------------


def diff_steps(
    before: Sequence[dict[str, object]], after: Sequence[dict[str, object]]
) -> tuple[tuple[StepChange, ...], int]:
    """Pure: steps compared by key; returns the changes in key order and the unchanged count."""
    old = {str(s["step_key"]): s for s in before}
    new = {str(s["step_key"]): s for s in after}
    out: list[StepChange] = []
    unchanged = 0
    for key in sorted(old.keys() | new.keys()):
        if key not in old:
            out.append(StepChange(key, "added"))
        elif key not in new:
            out.append(StepChange(key, "removed"))
        else:
            fields = tuple(f for f in COMPARED if old[key].get(f) != new[key].get(f))
            if fields:
                out.append(StepChange(key, "changed", fields))
            else:
                unchanged += 1
    return tuple(out), unchanged


async def _step_rows(session: AsyncSession, version_id: UUID) -> list[dict[str, object]]:
    steps = (
        await session.execute(select(ProgramStep).where(ProgramStep.version_id == version_id))
    ).scalars()
    return [{"step_key": s.step_key, **{f: getattr(s, f) for f in COMPARED}} for s in steps]


async def draft_changes(ctx: AuthContext, version_id: UUID) -> DraftChanges:
    """The draft's changes against the version it was drafted from (KNW-03 e grammar)."""
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        version = (
            await session.execute(
                select(MethodologyVersion).where(MethodologyVersion.id == version_id)
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFound(SUBJECT)
        against = version.drafted_from_version_id
        before = await _step_rows(session, against) if against else []
        after = await _step_rows(session, version_id)
    changes, unchanged = diff_steps(before, after)
    return DraftChanges(version_id, against, changes, unchanged)


__all__ = [
    "COMPARED",
    "EDITABLE",
    "DraftChanges",
    "DraftExists",
    "MandatoryLocked",
    "NotPublished",
    "StepChange",
    "StepHasRequests",
    "add_step",
    "create_draft",
    "diff_steps",
    "discard_draft",
    "draft_changes",
    "edit_step",
    "mandatory_guard",
    "remove_step",
    "set_mandatory",
]
