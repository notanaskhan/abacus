"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.routes import methodology_router, router
from abacus.modules.engagements.service import (
    EngagementMetadata,
    EngagementRef,
    MethodologyAlreadyApplied,
    MethodologyVersionView,
    TemplateVersionSummary,
    active_engagements,
    client_of,
    client_subquery,
    engagement_metadata,
    get_ref,
    lock_ref,
    pin_methodology,
    version_detail,
)
from abacus.modules.engagements.workbook import AccountRule, Area, TemplateItem, area_for
from abacus.modules.identity.api import register_active_engagements, register_engagement_client

# Identity owns ethical walls; this module owns which client an engagement belongs to (TASK-016).
register_engagement_client(client_subquery, client_of)
# SPEC-014: which engagements count for firm-level reads by engagement role (not archived).
register_active_engagements(active_engagements)

__all__ = [
    "AccountRule",
    "Area",
    "EngagementCreated",
    "EngagementMetadata",
    "EngagementRef",
    "MethodologyAlreadyApplied",
    "MethodologyVersionView",
    "TemplateItem",
    "TemplateVersionSummary",
    "area_for",
    "engagement_metadata",
    "get_ref",
    "lock_ref",
    "methodology_router",
    "pin_methodology",
    "router",
    "version_detail",
]
