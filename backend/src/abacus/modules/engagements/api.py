"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.ai_gateway import register_client_data_facts
from abacus.modules.engagements.audit_targets import AUDIT_KINDS, audit_engagements, visible_among
from abacus.modules.engagements.client_facts import client_engagements, engagements_section
from abacus.modules.engagements.conditions import functions_on, gates_of, service_line_of
from abacus.modules.engagements.contacts import (
    Designation,
    EngagementContact,
    attest_of,
    client_contact_names,
    client_entity_scope,
    client_scope,
    contact_portal_user,
    designate_contact,
    engagement_contacts,
    work_item_scope,
)
from abacus.modules.engagements.contract import (
    engagement_drafts_router,
    engagement_types_router,
    engagements_v2_router,
)
from abacus.modules.engagements.events import EngagementCreated, IndependenceRequested
from abacus.modules.engagements.gates import register_gates
from abacus.modules.engagements.hold_scope import (
    EngagementHoldFacts,
    engagement_hold_facts,
    engagements_in_hold_scope,
    work_item_engagement,
)
from abacus.modules.engagements.index_facts import work_item_index
from abacus.modules.engagements.roll_forward import (
    PriorItem,
    TemplateSeed,
    register_roll_forward_items,
)
from abacus.modules.engagements.routes import (
    firm_router,
    methodology_router,
    router,
    work_items_router,
)
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
    clients_of_engagements,
    engagement_label,
    engagement_metadata,
    engagement_resource_of,
    engagements_of_scope,
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
    Judgment,
    JudgmentSource,
    NewWorkItem,
    ProgressFact,
    ProgressSource,
    UnknownWorkItemKind,
    WorkItemProvider,
    gate_fact,
    judgments_of,
    progress_of,
    register_gate_provider,
    register_judgment_source,
    register_progress_source,
    register_work_item_kind,
    work_item_provider,
)
from abacus.modules.engagements.work_items import (
    AdvisoryProjectKind,
    AssuranceKind,
    PortalWorkItem,
    WorkItemExists,
    assurance_item_id,
    create_work_item,
    lock_engagement,
    portal_work_items,
    set_assurance_phase,
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
    register_attest_client,
    register_clients_of_engagements,
    register_engagement_client,
    register_engagement_resource,
    register_engagement_service_line,
    register_engagements_of_scope,
    register_independence,
    register_member_added,
    register_scope_resolver,
    register_work_item_functions,
)
from abacus.modules.identity.api import register_gates as register_condition_gates
from abacus.modules.organisations.api import (
    OverviewSection,
    register_client_engagements,
    register_open_requests,
    register_overview_section,
)

# Identity owns ethical walls; this module owns which client an engagement belongs to (TASK-016).
register_engagement_client(client_subquery, client_of)
# SPEC-036 (TASK-076): the AI gateway asks whether AI is off for an engagement.
register_client_data_facts(excluded=ai_excluded)
# SPEC-014: which engagements count for firm-level reads by engagement role (not archived).
register_active_engagements(active_engagements)
# P-07-T08: `register_open_requests` is re-exported for requests, keeping the plan's graph
# (requests -> engagements -> organisations; DEC-153).
# P-07-T08, T09: each client's open engagements, and CLI-02's Engagements overview section.
register_client_engagements(client_engagements)
register_overview_section(
    OverviewSection(
        code="engagements",
        kind="table",
        read_action="engagement.read_metadata",
        order=20,
        provide=engagements_section,
    )
)
# SPEC-025 (TASK-044): whoever joins a team is asked to confirm their independence.
register_member_added(request_independence)
# SPEC-025 (TASK-045): a staff engagement role reaches client data once its holder confirms.
register_independence(confirmed_subquery, confirmed_for)

register_gates()  # C1: G1 to G3 in the fail-closed gate slot
# F-03-T24: the facts the matrix conditions read (function_in, gates_met, in_scope).
register_work_item_functions(functions_on)
register_condition_gates(gates_of)
register_engagement_service_line(service_line_of)
register_attest_client(attest_of)  # F-03-T25: the client's derived attest flag (DEC-128)
# F-03-T26 (ADR-146): the client-access scope kinds engagements owns.
register_scope_resolver("work_item", work_item_scope)
# F-03-T22: the two kinds engagements owns; tax, closes and notices register theirs.
register_work_item_kind("assurance", AssuranceKind())
register_work_item_kind("advisory_project", AdvisoryProjectKind())
register_scope_resolver("client", client_scope)
register_scope_resolver("client_entity", client_entity_scope)
# F-03-T27 (ADR-145): the `client` scope kind reads through engagement visibility.
register_clients_of_engagements(clients_of_engagements)
register_engagements_of_scope(engagements_of_scope)
# F-03-T30: an engagement's Resource for platform's capabilities (archived from the row).
register_engagement_resource(engagement_resource_of)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    # The v2 contract stub (P-07-T05) first: its literal `/v1/engagements/index` must match before
    # the live `/v1/engagements/{engagement_id}` (tests/contracts/engagements_v2 holds the order).
    engagements_v2_router,
    engagement_types_router,
    engagement_drafts_router,
    router,
    work_items_router,
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
    "Designation",
    "Effort",
    "EngagementContact",
    "EngagementCreated",
    "EngagementHoldFacts",
    "EngagementMetadata",
    "EngagementNotOpen",
    "EngagementRef",
    "GateFact",
    "IndependenceRequested",
    "Judgment",
    "JudgmentSource",
    "MethodologyAlreadyApplied",
    "MethodologyVersionView",
    "NewWorkItem",
    "PortalWorkItem",
    "PriorItem",
    "ProgressFact",
    "ProgressSource",
    "StoredFile",
    "TemplateItem",
    "TemplateSeed",
    "TemplateVersionSummary",
    "UnknownWorkItemKind",
    "VersionNotLatest",
    "WorkItemExists",
    "WorkItemProvider",
    "area_for",
    "assurance_item_id",
    "attach_acceptance_file",
    "attach_letter_file",
    "audit_engagements",
    "check_facts",
    "client_contact_names",
    "contact_portal_user",
    "create_work_item",
    "designate_contact",
    "engagement_contacts",
    "engagement_hold_facts",
    "engagement_label",
    "engagement_metadata",
    "engagements_in_hold_scope",
    "entity_of",
    "firm_router",
    "gate_client_data",
    "gate_fact",
    "get_ref",
    "is_archived",
    "judgments_of",
    "lock_engagement",
    "lock_ref",
    "methodology_router",
    "methodology_version",
    "open_engagements",
    "pin_methodology",
    "portal_work_items",
    "progress_of",
    "publish_drafted_version",
    "register_auto_retrieval",
    "register_gate_provider",
    "register_judgment_source",
    "register_open_requests",
    "register_progress_source",
    "register_roll_forward_items",
    "register_work_item_kind",
    "require_open",
    "router",
    "run_auto_retrieval",
    "service_line_of",
    "set_assurance_phase",
    "stored_file",
    "version_detail",
    "visible_among",
    "work_item_engagement",
    "work_item_index",
    "work_item_provider",
]
