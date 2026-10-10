"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.modules.engagements.events import EngagementCreated, IndependenceRequested
from abacus.modules.engagements.roll_forward import (
    PriorItem,
    TemplateSeed,
    register_roll_forward_items,
)
from abacus.modules.engagements.routes import firm_router, methodology_router, router
from abacus.modules.engagements.service import (
    EngagementMetadata,
    EngagementRef,
    MethodologyAlreadyApplied,
    MethodologyVersionView,
    TemplateVersionSummary,
    active_engagements,
    client_of,
    client_subquery,
    engagement_label,
    engagement_metadata,
    entity_of,
    gate_client_data,
    get_ref,
    is_archived,
    lock_ref,
    open_engagements,
    pin_methodology,
    register_auto_retrieval,
    run_auto_retrieval,
    version_detail,
)
from abacus.modules.engagements.setup import (
    EngagementNotOpen,
    StoredFile,
    attach_acceptance_file,
    attach_letter_file,
    confirmed_for,
    confirmed_subquery,
    request_independence,
    require_open,
    stored_file,
)
from abacus.modules.engagements.workbook import AccountRule, Area, TemplateItem, area_for
from abacus.modules.identity.api import (
    register_active_engagements,
    register_engagement_client,
    register_independence,
    register_member_added,
)

# Identity owns ethical walls; this module owns which client an engagement belongs to (TASK-016).
register_engagement_client(client_subquery, client_of)
# SPEC-014: which engagements count for firm-level reads by engagement role (not archived).
register_active_engagements(active_engagements)
# SPEC-025 (TASK-044): whoever joins a team is asked to confirm their independence.
register_member_added(request_independence)
# SPEC-025 (TASK-045): a staff engagement role reaches client data once its holder confirms.
register_independence(confirmed_subquery, confirmed_for)

__all__ = [
    "AccountRule",
    "Area",
    "EngagementCreated",
    "EngagementMetadata",
    "EngagementNotOpen",
    "EngagementRef",
    "IndependenceRequested",
    "MethodologyAlreadyApplied",
    "MethodologyVersionView",
    "PriorItem",
    "StoredFile",
    "TemplateItem",
    "TemplateSeed",
    "TemplateVersionSummary",
    "area_for",
    "attach_acceptance_file",
    "attach_letter_file",
    "engagement_label",
    "engagement_metadata",
    "entity_of",
    "firm_router",
    "gate_client_data",
    "get_ref",
    "is_archived",
    "lock_ref",
    "methodology_router",
    "open_engagements",
    "pin_methodology",
    "register_auto_retrieval",
    "register_roll_forward_items",
    "require_open",
    "router",
    "run_auto_retrieval",
    "stored_file",
    "version_detail",
]
