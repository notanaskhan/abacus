"""TAX-02 "Run draft" and "Re-run draft…": the draft-run entry route (T-04-T55; T-04 AC-13.2, Q12;
DEC-68, DEC-4514). RED: it starts a `tax.return_drafter` run on a live return.

`POST /v1/tax-returns/{id}/draft-runs` is a person's request: never the agent, the system or
support, never a client. The matrix's `tax_return.draft_run` (the preparer and reviewer
functions on the return) is checked on the return's engagement with the return as the work item.
A return past final approval is the signer's record and is never redrafted (409
`draft_not_allowed`, the status named). The run itself is T-04-T25's
(`drafter_workflow.start_draft`): it proposes, a person decides (ADR-005), and its §7216 gate
holds on every tool call.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, engagement_resource
from abacus.modules.tax.drafter_workflow import start_draft

ACTION: Final = "tax_return.draft_run"
TARGET: Final = "tax_return"
# From final approval on, the return is the signer's (export.EXPORTABLE): no redraft.
LOCKED: Final = frozenset({"approved", "awaiting_signature", "filed", "accepted"})


class DraftNotAllowed(DomainConflict):
    """409: the return is past final approval; a draft would rewrite the signer's record."""

    code = "draft_not_allowed"


async def _status(ctx: AuthContext, return_id: UUID) -> str | None:
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text("SELECT status FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
            )
        ).scalar_one_or_none()
    return None if found is None else str(found)


async def run_draft(ctx: AuthContext, return_id: UUID) -> UUID:
    """Start a draft run for the person asking; returns the run (202 at the route)."""
    if ctx.client:
        raise NotFound(TARGET)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(ACTION, "role")
    for item in await work_item_facts(ctx, TARGET):
        if item.work_item_id == return_id:
            engagement_id = item.engagement_id
            break
    else:
        raise NotFound(TARGET)
    resource = replace(
        await engagement_resource(ctx.tenant, engagement_id), work_item_id=return_id
    )
    await authorise(ctx, ACTION, resource)
    status = await _status(ctx, return_id)
    if status is None:
        raise NotFound(TARGET)
    if str(status) in LOCKED:
        raise DraftNotAllowed(facts={"work_item_id": str(return_id), "status": str(status)})
    return await start_draft(ctx, return_id)
