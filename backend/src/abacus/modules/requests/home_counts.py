"""HOME-01's binders tile (I-01-T08; `home-and-gates.md` §3): the binders the viewer may read, by
status, narrowed to an office through the binder's engagement (DEC-30: a filter, never a
boundary). Closed binders are left out."""

from __future__ import annotations

from collections import Counter
from typing import Final, cast
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.api import gate_offices
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.platform.api import (
    HomeCount,
    HomeOfficeCount,
    HomeStatusCount,
    register_home_count,
)
from abacus.modules.requests.models import RequestList

_SHOWN: Final = ("draft", "published", "unpublished", "complete")


async def binders(viewer: object, office_id: UUID | None) -> HomeCount:
    ctx = cast(AuthContext, viewer)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(RequestList.engagement_id, RequestList.status).where(
                    RequestList.status.in_(_SHOWN),
                    visible(ctx, "binder.read", RequestList.engagement_id),
                )
            )
        ).all()
    offices = await gate_offices(ctx.tenant, [(e, None) for e in {e for e, _ in rows}])
    by_office = Counter(o for e, _ in rows if (o := offices.get((e, None))) is not None)
    if office_id is not None:
        rows = [(e, s) for e, s in rows if offices.get((e, None)) == office_id]
    by_status = Counter(s for _, s in rows)
    return HomeCount(
        total=len(rows),
        by_status=tuple(
            HomeStatusCount(s, by_status[s], f"status={s}") for s in _SHOWN if by_status[s]
        ),
        by_office=tuple(HomeOfficeCount(o, n) for o, n in sorted(by_office.items(), key=str)),
        target_filter=None,
    )


def register_home_counts() -> None:
    register_home_count("binders", binders)
