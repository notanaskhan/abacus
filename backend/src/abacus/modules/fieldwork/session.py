"""The agent procedure session (SPEC-044; TASK-109).

The session's plan is code's: fixed steps per procedure definition, in fixed words (ADR-111).
A person approves it (`procedure.run`), which starts the selection when there's none; every gate
after that is the existing flow's (SPEC-040): a person approves the sample, sends the request,
adopts the agent's row assessments and signs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.fieldwork.repository import (
    get_procedure,
    insert_session_event,
    newest_selection,
    plan_approval,
)
from abacus.modules.identity.api import AuthContext, authorise, names_of

_COMMON: Final = (
    ("approve", "A manager or the engagement partner approves the sample"),
    ("request", "One request to the client for the support of every selected item"),
    ("assess", "The agent reads each item's support and proposes, citing it"),
    ("adopt", "A preparer adopts the proposals as results, or records their own"),
    ("triage", "Exceptions, items needing input, and items passed"),
    ("workpaper", "The workpaper, signed by the preparer and a reviewer"),
)

PLANS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "journal_entry_testing": (
        ("population", "Build the journal entry population and tie it to the general ledger"),
        ("select", "Select entries by risk criteria and a seeded random sample"),
        *_COMMON,
    ),
    "unrecorded_liabilities": (
        ("population", "Take payments after year end and tie them to the bank-account credits"),
        ("select", "Select payments over each timing band's threshold, and check for a bill"),
        *_COMMON,
    ),
}


@dataclass(frozen=True)
class SessionView:
    plan: list[tuple[str, str]]
    approved_by_name: str | None
    approved_at: datetime | None


async def _procedure(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> str:
    async with tenant_session(ctx.tenant) as session:
        found = await get_procedure(session, procedure_id)
    if found is None or found.engagement_id != engagement_id:
        raise NotFound("procedure")
    return found.definition


async def session_of(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> SessionView:
    """AC-1: the plan, and whether (and by whom) it's approved."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    definition = await _procedure(ctx, engagement_id, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        approved = await plan_approval(session, procedure_id)
    name = (await names_of([approved.by_user])).get(approved.by_user, "") if approved else None
    return SessionView(
        list(PLANS.get(definition, _COMMON)),
        name,
        approved.created_at if approved else None,
    )


async def approve_plan(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> bool:
    """AC-2: record the approval; True when the selection should start (none yet)."""
    await _procedure(ctx, engagement_id, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "procedure.run", ref.resource())
        if await plan_approval(tx.session, procedure_id) is None:
            await insert_session_event(
                tx.session,
                tenant_id=ctx.tenant_id,
                procedure_id=procedure_id,
                kind="plan_approved",
                by_user=ctx.user_id,
            )
            tx.record("procedure_session.plan_approved", target=Target("procedure", procedure_id))
        selected = await newest_selection(tx.session, procedure_id)
    return selected is None
