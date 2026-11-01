"""A-04-T07: procedures and program tailoring, and pack validation (A-04 §3.1 AC1.9, §6 AC6.1;
SPEC-620 AC-9, AC-23; DEC-1867).

- **Instantiation.** An audit work item's procedures are its pinned methodology version's steps
  (level, mandatory, the workpaper a step points at as `linked_work`). They are written once, the
  first time anyone may read the program (AUD-04, KNW-03 d). The firm's system context writes
  them, audited `procedure.instantiated` with the count. Re-reading writes nothing, and a later
  version takes K-03's update path, never this one.
- **Tailoring.** A manager or the engagement partner (`procedure.tailor`) may tailor a
  non-mandatory step out, with a rationale, or back in. 409 `mandatory_step` for a mandatory
  step; 409 `version_conflict` when the row moved; 422 `rationale_required`. Audited
  `procedure.tailored`.
- **Pack validation** (by code, before any model call; A-04-T11's drafter runs it). Each step's
  `template_refs` resolve against the pinned version and the firm's template library (OQ-15): a
  `workpaper:<kind>` is a workpaper kind this module builds, and a `request:<key>` is a template
  some registered library holds. The first that does not resolve is the run's
  `pack_configuration_error`, in AUD-09 d's words.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import assurance_item_id, get_ref
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology.api import (
    VersionStep,
    VersionSteps,
    register_template_library,
    templates_held,
    version_steps,
)
from abacus.modules.workpapers.models import ProgramProcedure

WORKPAPER_KINDS: Final = frozenset(
    {"general_audit_planning", "risk_assessment", "internal_control", "service_organizations"}
)
# A request template's words in the error until K-03's library names its own templates.
_TEMPLATE_WORDS: Final = {"soc1_bridge_letter": "SOC 1 bridge-letter"}
_SYSTEM: Final = "workpapers.procedures"


class MandatoryStep(DomainConflict):
    """A mandatory step is never tailored (AC1.9)."""

    code = "mandatory_step"


class ProcedureMoved(DomainConflict):
    """The procedure changed since the caller read it."""

    code = "version_conflict"


class RationaleRequired(DomainInvalid):
    """Tailoring a step out needs the person's rationale."""

    code = "rationale_required"


class PackConfigurationError(DomainConflict):
    """The pinned version points at a template neither it nor the firm's library holds (AC6.1).
    `message` is AUD-09 d's sentence; the facts name the step and the reference."""

    code = "pack_configuration_error"

    def __init__(self, message: str, *, facts: dict[str, object]) -> None:
        super().__init__(facts=facts)
        self.message = message


@dataclass(frozen=True)
class PackError:
    program_code: str
    number: int
    ref: str
    message: str


@dataclass(frozen=True)
class ProcedureView:
    procedure: ProgramProcedure
    program_code: str
    number: int


def _words(ref: str) -> str:
    kind, _, key = ref.partition(":")
    return _TEMPLATE_WORDS.get(key, key.replace("_", " ")) if kind == "request" else key


def pack_message(step: VersionStep, ref: str, version_label: str) -> str:
    """AUD-09 d's words for a reference the pack does not include."""
    return (
        f"Pack configuration error: {step.program_code} step {step.number} points to a "
        f"{_words(ref)} template that {version_label} does not include. No evidence written."
    )


async def _workpaper_kinds(_tenant: TenantContext, refs: frozenset[str]) -> frozenset[str]:
    """This module's library: the workpaper kinds it builds."""
    return frozenset(r for r in refs if r.startswith("workpaper:") and r[10:] in WORKPAPER_KINDS)


register_template_library(_workpaper_kinds)


async def pack_errors(tenant: TenantContext, version_id: UUID) -> list[PackError]:
    """Every step reference the version and the firm's library cannot resolve, in step order."""
    version = await version_steps(tenant, version_id)
    wanted = {r for s in version.steps for r in s.template_refs}
    held = await templates_held(tenant, wanted) if wanted else frozenset[str]()
    return [
        PackError(s.program_code, s.number, ref, pack_message(s, ref, version.label))
        for s in version.steps
        for ref in s.template_refs
        if ref not in held
    ]


async def validate_pack(tenant: TenantContext, version_id: UUID) -> None:
    """Refuse with the first unresolved reference (`pack_configuration_error`), else pass."""
    errors = await pack_errors(tenant, version_id)
    if errors:
        first = errors[0]
        raise PackConfigurationError(
            first.message,
            facts={"program_code": first.program_code, "number": first.number, "ref": first.ref},
        )


def _linked(step: VersionStep) -> dict[str, object] | None:
    kinds = [r[10:] for r in step.template_refs if r.startswith("workpaper:")]
    return {"kind": "workpaper", "ref": kinds[0]} if kinds else None


async def _scope(ctx: AuthContext, engagement_id: UUID) -> tuple[UUID, UUID]:
    """The engagement's audit work item and its pinned version (404 without either)."""
    ref = await get_ref(ctx, engagement_id)
    work_item = await assurance_item_id(ctx.tenant, engagement_id)
    if work_item is None or ref.methodology_version_id is None:
        raise NotFound("procedures")
    return work_item, ref.methodology_version_id


async def ensure_procedures(
    ctx: AuthContext, engagement_id: UUID, work_item_id: UUID, version: VersionSteps
) -> int:
    """Write the version's steps as the work item's procedures once; how many were new."""
    system = TenantContext(ctx.tenant_id, "system", _SYSTEM)
    async with tenant_session(system) as session:
        have = set(
            (
                await session.execute(
                    select(ProgramProcedure.program_step_key).where(
                        ProgramProcedure.work_item_id == work_item_id
                    )
                )
            ).scalars()
        )
    missing = [s for s in version.steps if s.step_key not in have]
    if not missing:
        return 0
    async with uow(system) as tx:
        rows = [
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "work_item_id": work_item_id,
                "methodology_version_id": version.version_id,
                "program_step_key": s.step_key,
                "level": s.level,
                "mandatory": s.mandatory,
                "linked_work": _linked(s),
                "created_by": ctx.user_id,
            }
            for s in missing
        ]
        written = (
            await tx.session.execute(
                pg_insert(ProgramProcedure)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=["tenant_id", "work_item_id", "program_step_key"]
                )
                .returning(ProgramProcedure.id)
            )
        ).all()
        tx.record(
            "procedure.instantiated",
            target=Target("work_item", work_item_id),
            after=Ref(version_id=version.version_id, count=len(written)),
        )
    return len(written)


async def procedures_of(
    ctx: AuthContext, engagement_id: UUID, program: str | None = None
) -> list[ProcedureView]:
    """The work item's procedures in program and number order (one program when named). The
    route has authorised `procedure.read` and the flag."""
    work_item, version_id = await _scope(ctx, engagement_id)
    version = await version_steps(ctx.tenant, version_id)
    await ensure_procedures(ctx, engagement_id, work_item, version)
    order = {s.step_key: (s.program_position, s.number, s.program_code) for s in version.steps}
    async with tenant_session(ctx.tenant) as session:
        rows = list(
            (
                await session.execute(
                    select(ProgramProcedure).where(ProgramProcedure.work_item_id == work_item)
                )
            ).scalars()
        )
    views = [
        ProcedureView(p, order[p.program_step_key][2], order[p.program_step_key][1])
        for p in rows
        if p.program_step_key in order
        and (program is None or order[p.program_step_key][2] == program)
    ]
    return sorted(views, key=lambda v: order[v.procedure.program_step_key][:2])


async def tailor(
    ctx: AuthContext,
    engagement_id: UUID,
    procedure_id: UUID,
    *,
    expected_version: int,
    tailored: bool,
    rationale: str | None,
) -> ProcedureView:
    """A person's tailoring of one non-mandatory procedure (the route has authorised
    `procedure.tailor`)."""
    work_item, version_id = await _scope(ctx, engagement_id)
    text = (rationale or "").strip() or None
    if tailored and text is None:
        raise RationaleRequired(facts={"field": "rationale"})
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                select(ProgramProcedure)
                .where(
                    ProgramProcedure.id == procedure_id,
                    ProgramProcedure.work_item_id == work_item,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFound("procedure")
        if found.mandatory:
            raise MandatoryStep(facts={"program_step_key": found.program_step_key})
        if found.row_version != expected_version:
            raise ProcedureMoved(facts={"current": found.row_version})
        before = found.tailored
        found.tailored = tailored
        found.tailored_rationale = text if tailored else None
        found.row_version = found.row_version + 1
        tx.record(
            "procedure.tailored",
            target=Target("program_procedure", procedure_id),
            before=Ref(tailored=int(before)),
            after=Ref(tailored=int(tailored), row_version=found.row_version),
        )
    steps = {s.step_key: s for s in (await version_steps(ctx.tenant, version_id)).steps}
    step = steps.get(found.program_step_key)
    return ProcedureView(
        found,
        step.program_code if step is not None else "",
        step.number if step is not None else 1,
    )


__all__ = [
    "WORKPAPER_KINDS",
    "MandatoryStep",
    "PackConfigurationError",
    "PackError",
    "ProcedureMoved",
    "ProcedureView",
    "RationaleRequired",
    "ensure_procedures",
    "pack_errors",
    "pack_message",
    "procedures_of",
    "tailor",
    "validate_pack",
]
