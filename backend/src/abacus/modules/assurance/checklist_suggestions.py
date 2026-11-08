"""A-06-T16 seam (TASK-3395, DEC-2394): the agent's suggested disclosure checklist answers.

The agent proposes an answer through `agents.api.create_suggestion` with the statement document
as target (`disclosure_checklist`) and the item key as field. Reporting may not import agents
(BOUND-002), so assurance carries both halves: the `suggestion.created` subscriber mirrors a
pending yes or no on the item's row as `suggested`, and the applier writes it when a person
adopts it (`adopted`) or edits it (`answered`, theirs). The agent never answers (ADR-005): a
suggested item isn't counted as answered and can't be reviewed.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import UnitOfWork
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import AdoptedValue, pending_suggestion
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting.api import (
    CHECKLIST_SUGGESTION_TARGET,
    apply_suggested_answer,
    record_suggested_answer,
    statement_document_engagement,
    suggested_answer,
)

_ACTOR: Final = "assurance:checklist_suggestion"


async def on_suggestion_created(event: OutboxEvent) -> None:
    """Mirror a pending answer on its item; any other target's suggestion is not ours."""
    if event.payload.get("target_type") != CHECKLIST_SUGGESTION_TARGET:
        return
    tenant = TenantContext(event.tenant_id, "system", _ACTOR)
    found = await pending_suggestion(tenant, UUID(str(event.payload["suggestion_id"])))
    if found is None or found.target_type != CHECKLIST_SUGGESTION_TARGET:
        return
    answer = suggested_answer(found.proposed_value)
    if answer is None:
        return
    try:
        await record_suggested_answer(
            tenant, found.target_id, found.field_key, answer, found.suggestion_id
        )
    except DomainConflict:
        return  # a person answered the item meanwhile: their answer stands


async def apply_checklist_suggestion(
    tx: UnitOfWork, ctx: AuthContext, adopted: AdoptedValue
) -> None:
    """The `disclosure_checklist` suggestion applier, in the adopting unit of work."""
    answer = suggested_answer(adopted.value) or ""
    await apply_suggested_answer(
        tx,
        ctx,
        adopted.target_id,
        adopted.field_key,
        answer,
        suggestion_id=adopted.suggestion_id,
        edited=adopted.cause == "edit",
        citation_note=adopted.citation_note,
    )


SUBSCRIPTIONS: Final = {"suggestion.created": on_suggestion_created}
__all__ = [
    "CHECKLIST_SUGGESTION_TARGET",
    "SUBSCRIPTIONS",
    "apply_checklist_suggestion",
    "on_suggestion_created",
    "statement_document_engagement",
]
