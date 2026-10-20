"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.ai_gateway import register_client_data_facts
from abacus.modules.engagements.audit_targets import AUDIT_KINDS, audit_engagements, visible_among
from abacus.modules.engagements.events import EngagementCreated, IndependenceRequested
from abacus.modules.engagements.gates import register_gates
from abacus.modules.engagements.roll_forward import (
    PriorItem,
    TemplateSeed,
    register_roll_forward_items,
)
from abacus.modules.engagements.routes import firm_router, methodology_router, router
from abacus.modules.engagements.service import (
    ApprovedGuidance,
    CheckFacts,
    EngagementMetadata,
    EngagementRef,
    MethodologyAlreadyApplied,
    MethodologyVersionView,
    TemplateVersionSummary,
    VersionNotLatest,
    active_engagements,
    ai_excluded,
    check_facts,
    client_of,
    client_subquery,
    engagement_label,
    engagement_metadata,
    entity_of,
    gate_client_data,
    get_ref,
    is_archived,
    lock_ref,
    methodology_version,
    open_engagements,
    pin_methodology,
    publish_drafted_version,
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
from abacus.modules.engagements.slots import (
    GateFact,
    UnknownWorkItemKind,
    WorkItemProvider,
    gate_fact,
    register_gate_provider,
    register_work_item_kind,
    work_item_provider,
)
from abacus.modules.engagements.workbook import (
    AccountRule,
    Area,
    Effort,
    TemplateItem,
    area_for,
)
from abacus.modules.identity.api import (
    AbacusRouter,
    register_active_engagements,
    register_engagement_client,
    register_independence,
    register_member_added,
)

# Identity owns ethical walls; this module owns which client an engagement belongs to (TASK-016).
register_engagement_client(client_subquery, client_of)
# SPEC-036 (TASK-076): the AI gateway asks whether AI is off for an engagement.
register_client_data_facts(excluded=ai_excluded)
# SPEC-014: which engagements count for firm-level reads by engagement role (not archived).
register_active_engagements(active_engagements)
# SPEC-025 (TASK-044): whoever joins a team is asked to confirm their independence.
register_member_added(request_independence)
# SPEC-025 (TASK-045): a staff engagement role reaches client data once its holder confirms.
register_independence(confirmed_subquery, confirmed_for)

register_gates()  # C1: G1 to G3 in the fail-closed gate slot

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    methodology_router,
    firm_router,
)

__all__ = [
    "AUDIT_KINDS",
    "ROUTERS",
    "AccountRule",
    "ApprovedGuidance",
    "Area",
    "CheckFacts",
    "Effort",
    "EngagementCreated",
    "EngagementMetadata",
    "EngagementNotOpen",
    "EngagementRef",
    "GateFact",
    "IndependenceRequested",
    "MethodologyAlreadyApplied",
    "MethodologyVersionView",
    "PriorItem",
    "StoredFile",
    "TemplateItem",
    "TemplateSeed",
    "TemplateVersionSummary",
    "UnknownWorkItemKind",
    "VersionNotLatest",
    "WorkItemProvider",
    "area_for",
    "attach_acceptance_file",
    "attach_letter_file",
    "audit_engagements",
    "check_facts",
    "engagement_label",
    "engagement_metadata",
    "entity_of",
    "firm_router",
    "gate_client_data",
    "gate_fact",
    "get_ref",
    "is_archived",
    "lock_ref",
    "methodology_router",
    "methodology_version",
    "open_engagements",
    "pin_methodology",
    "publish_drafted_version",
    "register_auto_retrieval",
    "register_gate_provider",
    "register_roll_forward_items",
    "register_work_item_kind",
    "require_open",
    "router",
    "run_auto_retrieval",
    "stored_file",
    "version_detail",
    "visible_among",
    "work_item_provider",
]
