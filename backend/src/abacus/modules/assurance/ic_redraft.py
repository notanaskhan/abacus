"""The re-draft after Internal Control (A-04-T29; A-04 AC4.8, §4.4; DEC-2327). PROTECTED (red).

When the agent has written an Internal Control draft, the risks linked to it may read differently,
so a `risk` mode run proposes new rationale for them: a new suggestion, never a new value, and a
person decides it. The agent never writes a version (ADR-005), so "agent-written" is the moment its
`ic` run completes (`section_draft.finished`), not `workpaper.version_created`.

Started for the person who started the Internal Control run, through the same public entry and the
same authorisation, so someone who has since lost `workpaper.draft` starts nothing. Deduped on the
Internal Control run; the engagement's daily run cap and the gateway's budget apply as to any run.
No-op with `workpapers.drafting` off, or with no risk linked to Internal Control.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import WORKPAPERS_DRAFTING
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent
from abacus.modules.agents.api import (
    SectionDraftFinished,
    followed_up_running,
    start_section_draft,
)
from abacus.modules.assurance.ic_mode import MODE as IC_MODE
from abacus.modules.identity.api import AuthContext, Forbidden, member_context

_log = get_logger(__name__)
RISK_MODE: Final = "risk"
RISK_PAPER: Final = "risk_assessment"
KEY_PREFIX: Final = "ic_redraft"
# AUD-09, the Internal Control paper, as a response on the linkage matrix (AUD-08).
IC_TARGET: Final = "AUD-09"


async def _has_linked_risk(tenant: TenantContext, engagement_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT 1 FROM risk_linkages WHERE engagement_id = :e AND target_kind = 'workpaper' "
                "AND upper(target_ref) = :target AND removed_at IS NULL LIMIT 1"
            ),
            {"e": engagement_id, "target": IC_TARGET},
        )
    return found is not None


async def on_section_draft_finished(event: OutboxEvent) -> None:
    if event.payload["mode"] != IC_MODE:
        return
    tenant = TenantContext(event.tenant_id, "system", "assurance:ic_redraft")
    if not await flag_enabled(tenant, WORKPAPERS_DRAFTING):
        return
    engagement_id = UUID(str(event.payload["engagement_id"]))
    if not await _has_linked_risk(tenant, engagement_id):
        return
    person = await member_context(event.tenant_id, UUID(str(event.payload["initiator_user_id"])))
    if person is None:
        return
    # A refusal (the cap, no model, a person no longer allowed) ends here: the person can still use
    # AUD-08's "Draft with agent" (A-04 §1 item 3). Redelivery starts nothing more: the key is the run.
    from abacus.modules.workpapers.api import paper_of_kind

    with suppress(DomainConflict, Forbidden, NotFound):
        paper = await paper_of_kind(person, engagement_id, RISK_PAPER)
        await start_section_draft(
            person,
            engagement_id,
            paper,
            RISK_MODE,
            None,
            f"{KEY_PREFIX}:{event.payload['run_id']}",
        )
        return
    _log.info("ic_redraft.not_started")


async def revising(ctx: AuthContext, engagement_id: UUID) -> bool:
    """AUD-08 e: the re-draft after the latest Internal Control run is still running."""
    from abacus.modules.workpapers.api import paper_of_kind

    try:
        paper = await paper_of_kind(ctx, engagement_id, RISK_PAPER)
    except NotFound:
        return False
    return await followed_up_running(ctx.tenant_id, engagement_id, IC_MODE, paper, KEY_PREFIX)


SUBSCRIPTIONS: Final[dict[str, Handler]] = {
    SectionDraftFinished.event_type: on_section_draft_finished,
}
