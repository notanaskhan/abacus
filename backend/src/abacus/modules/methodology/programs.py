"""KNW-03's reads (K-01-T12; K-01 §3.4, §4.3): a version's programs, a program's steps with their
guidance, PBC links, level and locks, the step a citation anchor names, and the deterministic
program workbook.

An anchor is `step_key@v<n>`: the key is stable across versions (K-01-T05's lineage), so the same
key resolves to its step at whichever version the citation names. `step_at` is the C4 verifier's
read (registered from `agents`, which may import both evidence and methodology); it takes the
caller's session so the citation's unit of work reads under its own tenant.

Reads authorise `methodology.read` at the firm. A draft version's programs are the drafter's
firm's like any other read; the lifecycle decides what is editable, not what is visible here.
The rules count is 0 until K-03's rules land (a placeholder, never an invented number).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.methodology.models import (
    MethodologyVersion,
    Program,
    ProgramStep,
    ProgramStepPbcLink,
)
from abacus.modules.methodology.workbook_template import STAMP, normalised

READ = "methodology.read"
EXPORT_PROGRAMS = ("program_code", "program_name", "position")
EXPORT_STEPS = (
    "program_code",
    "step_key",
    "number",
    "text",
    "level",
    "mandatory",
    "lock_note",
    "assertions",
    "standard_refs",
    "pbc_positions",
)


@dataclass(frozen=True)
class ProgramView:
    id: UUID
    version_id: UUID
    code: str
    name: str
    position: int
    step_count: int
    mandatory_count: int
    flags_open: int
    counts_by_level: dict[str, int]


@dataclass(frozen=True)
class StepView:
    step: ProgramStep
    version: int
    pbc_positions: tuple[int, ...]

    @property
    def anchor(self) -> str:
        return f"{self.step.step_key}@v{self.version}"


@dataclass(frozen=True)
class CitedStep:
    """What the C4 verifier reads: the step a key names at one version."""

    version_id: UUID
    version: int
    program_id: UUID
    program_code: str
    step_id: UUID
    number: int
    text: str

    @property
    def anchor(self) -> str:
        return f"{self.step_key}@v{self.version}"

    step_key: str = ""


async def _version_number(session: AsyncSession, version_id: UUID) -> int:
    found = (
        await session.execute(
            select(MethodologyVersion.version).where(MethodologyVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if found is None:
        raise NotFound("methodology_version")
    return found


async def _program_views(session: AsyncSession, programs: Sequence[Program]) -> list[ProgramView]:
    ids = [p.id for p in programs]
    counts: dict[UUID, dict[str, int]] = {pid: {} for pid in ids}
    totals: dict[UUID, tuple[int, int, int]] = {pid: (0, 0, 0) for pid in ids}
    if ids:
        rows = await session.execute(
            select(
                ProgramStep.program_id,
                ProgramStep.level,
                func.count(),
                func.count().filter(ProgramStep.mandatory.is_(True)),
                func.count().filter(
                    ProgramStep.parse_flag.is_not(None), ProgramStep.flag_resolution.is_(None)
                ),
            )
            .where(ProgramStep.program_id.in_(ids))
            .group_by(ProgramStep.program_id, ProgramStep.level)
        )
        for program_id, level, n, mandatory, flags in rows.tuples():
            counts[program_id][level] = n
            total, locked, open_flags = totals[program_id]
            totals[program_id] = (total + n, locked + mandatory, open_flags + flags)
    return [
        ProgramView(
            p.id,
            p.version_id,
            p.code,
            p.name,
            p.position,
            totals[p.id][0],
            totals[p.id][1],
            totals[p.id][2],
            dict(sorted(counts[p.id].items())),
        )
        for p in programs
    ]


async def version_programs(ctx: AuthContext, version_id: UUID) -> list[ProgramView]:
    """KNW-02's Programs tree: a version's programs in position order, with their counts."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        await _version_number(session, version_id)
        programs = (
            await session.execute(
                select(Program).where(Program.version_id == version_id).order_by(Program.position)
            )
        ).scalars()
        return await _program_views(session, list(programs))


async def program(ctx: AuthContext, program_id: UUID) -> ProgramView:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = await session.get(Program, program_id)
        if found is None:
            raise NotFound("program")
        return (await _program_views(session, [found]))[0]


async def _links(session: AsyncSession, step_ids: Sequence[UUID]) -> dict[UUID, tuple[int, ...]]:
    found: dict[UUID, list[int]] = {sid: [] for sid in step_ids}
    if step_ids:
        rows = await session.execute(
            select(ProgramStepPbcLink.step_id, ProgramStepPbcLink.request_position)
            .where(ProgramStepPbcLink.step_id.in_(step_ids))
            .order_by(ProgramStepPbcLink.request_position)
        )
        for step_id, position in rows.tuples():
            found[step_id].append(position)
    return {k: tuple(v) for k, v in found.items()}


async def program_steps(ctx: AuthContext, program_id: UUID) -> list[StepView]:
    """KNW-03 a, b: the program's steps in number order, each with its anchor and PBC links."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = await session.get(Program, program_id)
        if found is None:
            raise NotFound("program")
        version = await _version_number(session, found.version_id)
        steps = list(
            (
                await session.execute(
                    select(ProgramStep)
                    .where(ProgramStep.program_id == program_id)
                    .order_by(ProgramStep.number)
                )
            ).scalars()
        )
        links = await _links(session, [s.id for s in steps])
        return [StepView(s, version, links[s.id]) for s in steps]


async def step_at(session: AsyncSession, step_key: str, version_id: UUID) -> CitedStep | None:
    """The step `step_key` names at `version_id`, or None (C4's `methodology_step` read)."""
    row = (
        await session.execute(
            select(ProgramStep, Program.code, MethodologyVersion.version)
            .join(Program, Program.id == ProgramStep.program_id)
            .join(MethodologyVersion, MethodologyVersion.id == ProgramStep.version_id)
            .where(ProgramStep.version_id == version_id, ProgramStep.step_key == step_key)
        )
    ).first()
    if row is None:
        return None
    step, code, version = cast(tuple[ProgramStep, str, int], tuple(row))
    return CitedStep(
        version_id=version_id,
        version=version,
        program_id=step.program_id,
        program_code=code,
        step_id=step.id,
        number=step.number,
        text=step.text,
        step_key=step.step_key,
    )


async def resolve_step(ctx: AuthContext, step_key: str, version_id: UUID) -> CitedStep:
    """C4: a `methodology_step` target to its program and step number (404 when the key has no
    step at that version)."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = await step_at(session, step_key, version_id)
    if found is None:
        raise NotFound("methodology_step")
    return found


def _sheet(
    workbook: Workbook, name: str, header: Sequence[str], rows: Sequence[Sequence[object]]
) -> None:
    sheet = cast(Worksheet, workbook.create_sheet(name))
    sheet.append([WriteOnlyCell(sheet, value=h) for h in header])
    for row in rows:
        sheet.append(list(row))


async def export_version(ctx: AuthContext, version_id: UUID) -> bytes:
    """The deterministic program workbook: the same version exports byte-identically (fixed
    document properties and zip times, rows in position and number order)."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        await _version_number(session, version_id)
        programs = list(
            (
                await session.execute(
                    select(Program)
                    .where(Program.version_id == version_id)
                    .order_by(Program.position)
                )
            ).scalars()
        )
        codes = {p.id: p.code for p in programs}
        steps = list(
            (
                await session.execute(
                    select(ProgramStep)
                    .where(ProgramStep.version_id == version_id)
                    .order_by(ProgramStep.program_id, ProgramStep.number)
                )
            ).scalars()
        )
        links = await _links(session, [s.id for s in steps])
    order = {p.id: p.position for p in programs}
    steps.sort(key=lambda s: (order.get(s.program_id, 0), s.number))
    workbook = Workbook(write_only=True)
    properties = workbook.properties
    properties.creator = "platform"
    properties.lastModifiedBy = "platform"
    properties.created = STAMP.replace(tzinfo=None)
    properties.modified = STAMP.replace(tzinfo=None)
    _sheet(workbook, "Programs", EXPORT_PROGRAMS, [(p.code, p.name, p.position) for p in programs])
    _sheet(
        workbook,
        "Steps",
        EXPORT_STEPS,
        [
            (
                codes[s.program_id],
                s.step_key,
                s.number,
                s.text,
                s.level,
                "yes" if s.mandatory else "no",
                s.lock_note or "",
                "; ".join(s.assertions),
                "; ".join(s.standard_refs),
                "; ".join(str(p) for p in links[s.id]),
            )
            for s in steps
        ],
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return normalised(buffer.getvalue())
