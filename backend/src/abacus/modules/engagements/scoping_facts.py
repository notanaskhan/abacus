"""The engagement profile's scoping sources (K-03-T18; TASK-9011; SHT-03; DEC-6017).

Registered as methodology's `engagements` scoping-source provider:

- `engagement.profile.group_audit` — "Engagement > Profile > Group audit (SAS 149)": `yes` when
  an assurance work item of the engagement is a group audit, `no` when it has assurance work
  and none is; unanswered without assurance work.
- `engagement.profile.first_year` — "Engagement > Profile > First-year engagement": `yes` when
  the engagement rolls forward from no prior engagement.

The reader must hold `scoping.read` on the engagement; a walled or absent engagement is 404
(INV-3), so a preview never reveals another engagement's answers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.methodology.api import scoping_rules as sr

_SEP: Final = " \u203a "  # the menus' separator (SHT-03)

GROUP_AUDIT: Final = "engagement.profile.group_audit"
FIRST_YEAR: Final = "engagement.profile.first_year"
_YES_NO: Final = ("yes", "no")
CATALOGUE: Final[tuple[sr.Source, ...]] = (
    sr.Source(
        GROUP_AUDIT,
        _SEP.join(("Engagement", "Profile", "Group audit (SAS 149)")),
        "engagement_fact",
        _YES_NO,
    ),
    sr.Source(
        FIRST_YEAR,
        _SEP.join(("Engagement", "Profile", "First-year engagement")),
        "engagement_fact",
        _YES_NO,
    ),
)
_FACTS: Final = text(
    "SELECT e.prior_engagement_id, "
    "(SELECT bool_or(a.is_group_audit) FROM assurance_work_items a JOIN work_items w "
    "ON w.id = a.work_item_id WHERE w.engagement_id = e.id) AS group_audit "
    "FROM engagements e WHERE e.id = :e"
)


async def authorise_reader(ctx: AuthContext, engagement_id: UUID) -> None:
    """`scoping.read` on the engagement, or 404 (never 403: a wall hides existence)."""
    from abacus.modules.engagements.service import engagement_resource_of

    resource = await engagement_resource_of(ctx.tenant, engagement_id)
    try:
        await authorise(ctx, "scoping.read", resource)
    except Forbidden:
        raise NotFound("engagement") from None


class EngagementFacts:
    def knows(self, key: str) -> bool:
        return key in (GROUP_AUDIT, FIRST_YEAR)

    async def catalogue(self, ctx: AuthContext) -> Sequence[sr.Source]:
        del ctx
        return CATALOGUE

    async def answers(self, ctx: AuthContext, engagement_id: UUID) -> Mapping[str, str | None]:
        await authorise_reader(ctx, engagement_id)
        async with tenant_session(ctx.tenant) as session:
            row = (await session.execute(_FACTS, {"e": engagement_id})).first()
        if row is None:
            raise NotFound("engagement")
        group = None if row.group_audit is None else ("yes" if row.group_audit else "no")
        return {GROUP_AUDIT: group, FIRST_YEAR: "yes" if row.prior_engagement_id is None else "no"}


def register() -> None:
    sr.register_scoping_source("engagements", EngagementFacts())


__all__ = ["CATALOGUE", "FIRST_YEAR", "GROUP_AUDIT", "EngagementFacts", "authorise_reader"]
