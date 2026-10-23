"""What engagements tells the clients family (P-07-T08, T09): each client's open engagements
and their service lines, and CLI-02's Engagements overview section. Registered in `api.py`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.models import Engagement
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.organisations.api import OverviewItem, SectionRows

# Neither archived nor declined: what CLI-01's service lines and CLI-02's menu count.
_CLOSED = ("archived", "declined")


def client_engagements() -> Select[UUID, UUID, str, str, str]:
    """`(client_id, engagement_id, name, status, service_line)` per open engagement."""
    return select(
        Engagement.client_id,
        Engagement.id.label("engagement_id"),
        Engagement.name,
        Engagement.status,
        Engagement.service_line,
    ).where(Engagement.status.not_in(_CLOSED))


async def engagements_section(ctx: AuthContext, client_id: UUID) -> SectionRows:
    """The client's engagements the caller may see, newest period first, with their status."""
    async with tenant_session(ctx.tenant) as session:
        rows = (
            (
                await session.execute(
                    select(
                        Engagement.id,
                        Engagement.name,
                        Engagement.status,
                        Engagement.fiscal_period_end,
                    )
                    .where(
                        Engagement.client_id == client_id,
                        Engagement.status != "archived",
                        visible(ctx, "engagement.read_metadata", Engagement.id),
                    )
                    .order_by(Engagement.fiscal_period_end.desc(), Engagement.id)
                )
            )
            .tuples()
            .all()
        )
    return SectionRows(
        [
            OverviewItem(
                key="engagement",
                text=name,
                on=period_end,
                pill_object="engagement",
                pill_code=status,
                ref_type="engagement",
                ref_id=eid,
            )
            for eid, name, status, period_end in rows
        ],
        total=len(rows),
    )
