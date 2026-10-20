"""Adopting the agent's row assessments as results (SPEC-044 AC-4; TASK-109).

A person adopts: each chosen row with an assessment and no result yet becomes a result recorded by
that person, marked with the assessment it came from. `explained` is supported; `not_explained`
is an exception with a note; `unclear` stays for a person. The agent records nothing (ADR-005);
the sample-approval gate applies in `record_result` (SPEC-040 AC-3).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.modules.agents.repository import newest_assessments
from abacus.modules.engagements.api import get_ref
from abacus.modules.fieldwork.api import items_with_results, record_result, selection_item_ids
from abacus.modules.identity.api import AuthContext, authorise

_NOTE: Final = "The agent found the support doesn't explain the entry"


async def adopt(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, item_ids: Sequence[UUID] | None
) -> int:
    """How many rows were adopted."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "entry_assessment.adopt", ref.resource())
    items = await selection_item_ids(ctx, engagement_id, procedure_id)
    if item_ids:
        wanted = set(item_ids)
        items = [i for i in items if i in wanted]
    done = await items_with_results(ctx, engagement_id, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        assessments = await newest_assessments(session, ctx, engagement_id, items)
    adopted = 0
    for a in assessments:
        if a.selected_item_id in done or a.shown_verdict not in ("explained", "not_explained"):
            continue
        supported = a.shown_verdict == "explained"
        await record_result(
            ctx,
            engagement_id,
            procedure_id,
            a.selected_item_id,
            result="supported" if supported else "exception",
            note=None if supported else f"{_NOTE}: {a.rationale}"[:2000],
            evidence_ids=[],
            adopted_assessment_id=a.id,
        )
        adopted += 1
    return adopted
