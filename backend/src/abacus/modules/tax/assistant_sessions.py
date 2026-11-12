"""The return's assistant sessions (T-04-T37; T-04 §4.3, §6; TAX-08; P-10-T43; DEC-4316).

A TAX-08 thread is a workbench session bound to one tax return (`("tax_return", id)` in its
context), on the return's engagement, running `tax.assistant`. Opening one needs the person's
`tax_return.read` on the return; before anything runs the capability's availability is read (C19's
§7216 consents, the boundary facts, pauses: P-10-T45), and an unavailable assistant answers its
reason (DF-04's agents-off state) with no session and no model call. History lists the person's
own threads on the return.
"""

from __future__ import annotations

from typing import ClassVar, Final
from uuid import UUID

from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.agents.api import capability_ready
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.workbench.api import SessionSummary, open_session, sessions_for_subject

CAPABILITY: Final = "tax.assistant"
SUBJECT: Final = "tax_return"


class AssistantUnavailable(DomainConflict):
    """DF-04: the assistant can't run on this return now (`facts.reason`: consent_7216, …)."""

    code: ClassVar[str] = "assistant_unavailable"


async def _engagement(ctx: AuthContext, return_id: UUID) -> UUID:
    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")
    ref = await get_ref(ctx, engagement)  # a wall answers 404
    await authorise(ctx, "tax_return.read", ref.resource())
    return engagement


async def open_assistant(ctx: AuthContext, return_id: UUID, title: str) -> UUID:
    engagement = await _engagement(ctx, return_id)
    ready, reason = await capability_ready(ctx, engagement, CAPABILITY)
    if not ready:
        raise AssistantUnavailable(facts={"reason": reason or "capability_unavailable"})
    return await open_session(
        ctx,
        title=title,
        origin="manual",
        engagement_id=engagement,
        capability=CAPABILITY,
        subject=(SUBJECT, return_id),
    )


async def assistant_history(ctx: AuthContext, return_id: UUID) -> list[SessionSummary]:
    await _engagement(ctx, return_id)
    return await sessions_for_subject(ctx, SUBJECT, return_id)
