"""Notice response dates as filing-deadline facts (T-08-T20; TASK-8915; FD-1; HOME-03;
DEC-5917). Registered to platform's slot as kind `notice_response`; practice never imports
notices. One fact per open notice with a respond-by date: "CP2000 response · 2024", the client,
the assignee as owner and the engagement partner as signer; done once the response is sent (or
the notice closed). Metadata only: no amount, no TIN digits."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow

KIND: Final = "notice_response"
DONE: Final = frozenset({"sent", "awaiting_irs", "closed"})
_ROWS: Final = text(
    "SELECT work_item_id, engagement_id, client_id, notice_code, tax_year, status, respond_by, "
    "assignee_user_id FROM notices WHERE respond_by BETWEEN :start AND :end "
    "AND status <> 'escalated' ORDER BY respond_by, work_item_id"
)


async def notice_deadlines(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
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
        year = "" if r.tax_year is None else f" · {r.tax_year}"
        out.append(
            FilingDeadlineFact(
                source_kind=KIND,
                source_ref=f"notice:{r.work_item_id}",
                filing_label=f"{r.notice_code} response{year}",
                client_id=cast("UUID | None", r.client_id) or (None if f is None else f.client_id),
                office_id=None if f is None else f.office_id,
                service_line="tax",
                original_due_on=r.respond_by,
                due_on=r.respond_by,
                stage_code=str(r.status),
                owner_user_ids=()
                if r.assignee_user_id is None
                else (cast(UUID, r.assignee_user_id),),
                signer_user_id=next((u for u, x in team if str(x) == "engagement_partner"), None),
                done=str(r.status) in DONE,
                work_item_id=cast(UUID, r.work_item_id),
            )
        )
    return out


def register() -> None:
    from abacus.modules.platform.api import register_filing_deadline_source

    register_filing_deadline_source(KIND, notice_deadlines)


__all__ = ["KIND", "notice_deadlines", "register"]
