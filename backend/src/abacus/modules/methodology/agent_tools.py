"""What `methodology.read_step` reads (P-10-T28; C17; ADR-233): one program step of a
methodology version (its text, assertions, standards and dependencies). The tool is declared by
`engagements`, which knows the version an engagement is pinned to; the model names the step only,
never a version id. The runtime has authorised `methodology.read` on the engagement.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from abacus.kernel.agent_tools import ToolCaller
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.methodology.models import ProgramStep

Int = classified("internal")
Conf = classified("confidential")


class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    step_key: Annotated[
        str, Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_.\-]+$"), Int
    ]


class StepOut(BaseModel):
    id: Annotated[UUID, Int]
    step_key: Annotated[str, Int]
    number: Annotated[int, Int]
    text: Annotated[str, Conf]
    level: Annotated[str, Int]
    mandatory: Annotated[bool, Int]
    assertions: Annotated[list[str], Int]
    standard_refs: Annotated[list[str], Int]
    depends_on_step_keys: Annotated[list[str], Int]
    lock_note: Annotated[str | None, Conf] = None


async def step_of_version(caller: ToolCaller, version_id: UUID, step_key: str) -> StepOut:
    """One step of a methodology version, for the `methodology.read_step` tool that
    `engagements` declares with the engagement's pinned version (methodology never imports
    engagements)."""
    async with tenant_session(caller.tenant) as session:
        step = (
            await session.execute(
                select(ProgramStep).where(
                    ProgramStep.version_id == version_id, ProgramStep.step_key == step_key
                )
            )
        ).scalar_one_or_none()
    if step is None:
        raise NotFound("program_step")
    return StepOut(
        id=step.id,
        step_key=step.step_key,
        number=step.number,
        text=step.text,
        level=step.level,
        mandatory=step.mandatory,
        assertions=list(step.assertions),
        standard_refs=list(step.standard_refs),
        depends_on_step_keys=list(step.depends_on_step_keys),
        lock_note=step.lock_note,
    )
