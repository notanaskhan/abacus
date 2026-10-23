"""The engagements part of the home: work cards with the client stage tracker, and the team with
client-facing role codes (P-08 §2.2: C1 work items and C2 codes; OQ-5 derives the day-to-day
contact per work-item kind).

A work item shows a card only when its kind carries a C2 lifecycle code. Today that is assurance
(the `audit_engagement` phase); a tax return's subtype has no lifecycle yet (`tax.kind`), so its
card waits for the module that records one, as P-08 §2.2 hides any card whose source has not
shipped. Close cards are C-01's.
"""

from __future__ import annotations

from typing import Final

from abacus.modules.engagements.api import PortalWorkItem
from abacus.modules.identity.api import AuthContext, engagement_team
from abacus.modules.portal import stages
from abacus.modules.portal.codes import TeamRoleCode
from abacus.modules.portal.home_sources import (
    HomePart,
    HomeScope,
    HomeTeamMember,
    Pill,
    Stage,
    WorkCard,
    register_home_source,
)

# Firm engagement roles in the order the team lists them; client roles are never shown.
_ORDER: Final = ("engagement_partner", "manager", "senior", "staff")
_TAX: Final[dict[str, TeamRoleCode]] = {
    "engagement_partner": "partner_signs_return",
    "manager": "manager_reviews_return",
    "senior": "preparer",
    "staff": "preparer",
}
_ASSURANCE: Final[dict[str, TeamRoleCode]] = {
    "engagement_partner": "engagement_partner",
    "manager": "manager",
    "senior": "day_to_day_contact",
    "staff": "preparer",
}


def _card(item: PortalWorkItem) -> WorkCard | None:
    if item.kind != "assurance" or item.phase is None:
        return None
    view = stages.client_view("soc2" if item.assurance_type == "soc2" else "audit", item.phase)
    if view is None:
        return None  # released: an Earlier row, not a card
    return WorkCard(
        item.id,
        item.kind,
        item.name,
        Pill(view.pill, view.variant),
        [Stage(s.code, s.state) for s in view.stages],
    )


async def engagements_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    for item in scope.work_items:
        card = _card(item)
        if card is not None:
            part.work_cards.append(card)
    seen: set[object] = set()
    for engagement_id in scope.engagements:
        kinds = {i.kind for i in scope.work_items if i.engagement_id == engagement_id}
        codes = _TAX if "tax_return" in kinds else _ASSURANCE
        team = [m for m in await engagement_team(ctx, engagement_id) if m.role in codes]
        team.sort(key=lambda m: (_ORDER.index(m.role), m.display_name))
        day_to_day = codes is _TAX
        for member in team:
            if member.user_id in seen:
                continue
            seen.add(member.user_id)
            role = codes[member.role]
            if day_to_day and role == "preparer":  # the first preparer is the day-to-day contact
                role, day_to_day = "preparer_day_to_day", False
            part.team.append(HomeTeamMember(member.user_id, member.display_name, role))
    return part


register_home_source("engagements", engagements_source)
