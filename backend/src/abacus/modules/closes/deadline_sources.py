"""Close due dates as filing-deadline facts (T-08-T20; TASK-8915; FD-1; HOME-03; DEC-5917).
Registered to platform's slot as kind `close`; practice builds the read model and never imports
closes. One fact per close with a due date: "June 2026 close", the engagement's client and
office, its preparers and reviewers as owners and its partner as signer; done once delivered or
locked. Metadata only."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow

KIND: Final = "close"
DONE: Final = frozenset({"delivered", "locked"})
OWNER_ROLES: Final = frozenset({"senior", "staff", "reviewer", "manager"})
_ROWS: Final = text(
    "SELECT work_item_id, engagement_id, period, status, due_on FROM closes "
    "WHERE due_on BETWEEN :start AND :end AND coalesce(on_hold, false) = false "
    "ORDER BY due_on, work_item_id"
)


async def close_deadlines(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    from abacus.modules.closes.registrations import month_label
    from abacus.modules.engagements.api import engagement_retention_facts
    from abacus.modules.identity.api import team_of

    t = cast(TenantContext, tenant)
    async with tenant_session(t) as session:
        rows = (await session.execute(_ROWS, {"start": window.start, "end": window.end})).all()
    engagements = sorted({cast(UUID, r.engagement_id) for r in rows}, key=str)
    facts = await engagement_retention_facts(t, engagements)
    out: list[FilingDeadlineFact] = []
    for r in rows:
        engagement = cast(UUID, r.engagement_id)
        team = await team_of(t.tenant_id, engagement)
        f = facts.get(engagement)
        out.append(
            FilingDeadlineFact(
                source_kind=KIND,
                source_ref=f"close:{r.work_item_id}",
                filing_label=f"{month_label(str(r.period))} close",
                client_id=None if f is None else f.client_id,
                office_id=None if f is None else f.office_id,
                service_line="cas",
                original_due_on=r.due_on,
                due_on=r.due_on,
                stage_code=str(r.status),
                owner_user_ids=tuple(
                    sorted({u for u, x in team if str(x) in OWNER_ROLES}, key=str)
                ),
                signer_user_id=next((u for u, x in team if str(x) == "engagement_partner"), None),
                done=str(r.status) in DONE,
                work_item_id=cast(UUID, r.work_item_id),
            )
        )
    return out


def register() -> None:
    from abacus.modules.platform.api import register_filing_deadline_source

    register_filing_deadline_source(KIND, close_deadlines)


__all__ = ["KIND", "close_deadlines", "register"]
