"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

from abacus.ai_gateway import DataSubject, register_client_data_facts, register_tri_consent_check
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent
from abacus.kernel.uow.placement import register_engagement_placer
from abacus.modules.engagements.acceptance import (
    NewCondition,
    acceptance_record,
    add_flag,
    complete_manual_check,
    decide_acceptance,
    request_manual_check,
    send_to_partner,
    update_answers,
)
from abacus.modules.engagements.acceptance_contract import (
    acceptance_router,
    independence_router,
    team_roles_router,
)
from abacus.modules.engagements.audit_placement import place_engagements
from abacus.modules.engagements.audit_targets import AUDIT_KINDS, audit_engagements, visible_among
from abacus.modules.engagements.client_facts import client_engagements, engagements_section
from abacus.modules.engagements.client_import_activities import (
    ACTIVITIES,
    SCHEDULES,
    WORKFLOWS,
)
from abacus.modules.engagements.conditions import (
    functions_on,
    gates_of,
    service_line_column,
    service_line_of,
)
from abacus.modules.engagements.contacts import (
    Designation,
    EngagementContact,
    attest_of,
    client_contact_names,
    client_contact_organisations,
    client_contact_organisations_of_users,
    client_entity_scope,
    client_scope,
    contact_portal_user,
    designate_contact,
    engagement_contacts,
    invitation_parties,
    mfa_designated,
    work_item_scope,
)
from abacus.modules.engagements.contract import (
    engagement_drafts_router,
    engagement_types_router,
    engagements_v2_router,
)
from abacus.modules.engagements.drafts import create_draft, draft_visible, start_acceptance
from abacus.modules.engagements.events import EngagementCreated, IndependenceRequested
from abacus.modules.engagements.gates import recorded_letter, register_gates
from abacus.modules.engagements.hold_scope import (
    EngagementHoldFacts,
    engagement_hold_facts,
    engagements_in_hold_scope,
    work_item_engagement,
)
from abacus.modules.engagements.home_work import AssignedWork, assigned_work
from abacus.modules.engagements.human_gates import (
    ACCEPTANCE_DECISION_DUE,
    EQR_ELIGIBILITY_DUE,
    INDEPENDENCE_CONCLUSION_DUE,
    INDEPENDENCE_CONFIRMATION_DUE,
    DueGate,
    acceptance_decisions_due,
    eqr_eligibility_due,
    independence_conclusions_due,
    independence_confirmations_due,
)
from abacus.modules.engagements.independence import (
    conclude_independence,
    confirm_independence,
)
from abacus.modules.engagements.index_facts import (
    assurance_index,
    gate_offices,
    letters_sent,
    methodology_usage,
    work_item_index,
)
from abacus.modules.engagements.intake import commit_intake as commit_client_intake
from abacus.modules.engagements.intake import draft_visible as intake_draft_visible
from abacus.modules.engagements.intake import subject_names as intake_subject_names
from abacus.modules.engagements.intake_contract import (
    client_imports_router,
    client_intake_drafts_router,
    dedupe_router,
)
from abacus.modules.engagements.letter_contract import letter_router
from abacus.modules.engagements.pilot_w4 import w4_portal_activation
from abacus.modules.engagements.roll_forward import (
    PriorItem,
    TemplateSeed,
    register_roll_forward_items,
)
from abacus.modules.engagements.roll_forward_contract import roll_forward_router
from abacus.modules.engagements.roll_forward_v2 import register_draft_request_copy
from abacus.modules.engagements.routes import (
    firm_router,
    router,
    work_items_router,
)
from abacus.modules.engagements.service import (
    CheckFacts,
    EngagementMetadata,
    EngagementRef,
    MethodologyAlreadyApplied,
    active_engagements,
    add_to_team,
    ai_excluded,
    all_engagement_ids,
    change_team_role,
    check_facts,
    client_of,
    client_subquery,
    clients_of_engagements,
    engagement_label,
    engagement_metadata,
    engagement_resource_of,
    engagements_of_entity,
    engagements_of_scope,
    entity_of,
    gate_client_data,
    get_ref,
    is_archived,
    lock_ref,
    open_engagements,
    pin_methodology,
    pin_methodology_on,
    register_auto_retrieval,
    remove_from_team,
    run_auto_retrieval,
    set_ai_exclusion_of,
)
from abacus.modules.engagements.setup import (
    EngagementNotOpen,
    StoredFile,
    answer_independence,
    attach_letter_file,
    attest_column,
    confirmed_for,
    confirmed_subquery,
    g2_blocks,
    independence_cleared,
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
    evidence_readable,
    gate_fact,
    gate_registered,
    judgments_of,
    progress_of,
    register_evidence_readable,
    register_gate_provider,
    register_judgment_source,
    register_progress_source,
    register_work_item_kind,
    replace_gate_provider,
    work_item_provider,
)
from abacus.modules.engagements.team import (
    approve_eqr_eligibility,
    approve_team,
    assign_eqr,
    team_approval,
)
from abacus.modules.engagements.work_item_facts import (
    WorkItemFacts,
    work_item_facts,
    work_item_offices,
)
from abacus.modules.engagements.work_items import (
    WORK_ITEM_FUNCTIONS,
    AdvisoryProjectKind,
    AssuranceItem,
    AssuranceKind,
    PortalWorkItem,
    WorkItemExists,
    archive_work_item,
    assign_work_item,
    assurance_item,
    assurance_item_id,
    client_tax_years,
    client_tri_subjects,
    create_work_item,
    end_wall_assignments,
    holds_tax_return,
    lock_assurance_item,
    lock_engagement,
    mfa_tri_scope,
    portal_work_items,
    set_assurance_profile,
    wall_assignment_count,
)
from abacus.modules.identity.api import (
    AbacusRouter,
    register_active_engagements,
    register_attest_client,
    register_attest_client_column,
    register_clients_of_engagements,
    register_contact_activation,
    register_engagement_client,
    register_engagement_resource,
    register_engagement_service_line,
    register_engagement_service_line_column,
    register_engagements_of_scope,
    register_independence,
    register_invitation_parties,
    register_member_added,
    register_mfa_requirement,
    register_scope_resolver,
    register_wall_assignments,
    register_work_item_functions,
)
from abacus.modules.identity.api import register_gates as register_condition_gates
from abacus.modules.methodology.api import (
    METHODOLOGY_USAGE_TYPE,
    AccountRule,
    ApprovedGuidance,
    Area,
    Effort,
    MethodologyVersionView,
    TemplateItem,
    TemplateVersionSummary,
    VersionNotLatest,
    area_for,
    methodology_version,
    publish_drafted_version,
    register_usage_counter,
    version_detail,
)
from abacus.modules.organisations.api import (
    MaskedTinOut,  # N-01: the masked TIN shape, re-exported for evidence's file drawer
    OverviewSection,
    TriSubject,
    activate_contact,
    covering_consents,
    readable_client,  # P-07-T57: re-exported for audit_trail's Activity lines (DEC-718)
    register_client_engagements,
    register_conflict_subject,
    register_conflict_subject_names,
    register_open_requests,
    register_overview_section,
    register_screening_evidence,
)
from abacus.modules.platform.api import register_pilot_metric_source

# Identity owns ethical walls; this module owns which client an engagement belongs to (TASK-016).
register_engagement_client(client_subquery, client_of)
# G-02-T08 gap (DEC-458): the unit of work places engagement-scoped audit events.
register_engagement_placer(place_engagements)
# SPEC-036 (TASK-076): the AI gateway asks whether AI is off for an engagement.
# P-06-T20 security review (DEC-324): tax-return work reaches no model without consent.
register_client_data_facts(excluded=ai_excluded, tax_return=holds_tax_return)


# T-01-T11 (C19 condition 6): organisations answers whether a context's TRI subjects hold both
# §7216 consents; it never imports the gateway (P-07-T04), so the registration is made here.
async def _tri_consents(
    tenant: TenantContext, subjects: tuple[DataSubject, ...], at: datetime
) -> tuple[UUID, ...] | None:
    return await covering_consents(
        tenant, [TriSubject(s.entity_id, s.tax_year) for s in subjects], at
    )


register_tri_consent_check(_tri_consents)
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
# K-01-T03: KNW-01's "Used by n engagements", over `visible()` (walls never counted).
register_usage_counter(METHODOLOGY_USAGE_TYPE, methodology_usage)
# P-07-T36 review (DEC-375, L4): what a conflict check or screening record may name.
register_conflict_subject("engagement_draft", draft_visible)
register_conflict_subject("client_intake_draft", intake_draft_visible)  # P-07-T42
# P-07-T42 security review (H1): a check on an intake draft searches the draft's own names.
register_conflict_subject_names("client_intake_draft", intake_subject_names)
register_screening_evidence(evidence_readable)
# F-03-T24: the facts the matrix conditions read (function_in, gates_met, in_scope).
register_work_item_functions(functions_on)
# G-01-T09 (AC8.5): a wall's preview counts, and its consumer ends, the person's assignments.
register_wall_assignments(wall_assignment_count, end_wall_assignments)
register_condition_gates(gates_of)
register_engagement_service_line(service_line_of)
# G-01-T12 (DEC-380): the same as SQL, for `visible()`'s service-line reach.
register_engagement_service_line_column(service_line_column)
register_attest_client(attest_of)  # F-03-T25: the client's derived attest flag (DEC-128)
# P-07-T24 (ADR-164 item 3): the same flag as SQL, for `visible()` under `g2_blocks_view`.
register_attest_client_column(attest_column)
# F-03-T26 (ADR-146): the client-access scope kinds engagements owns.
register_scope_resolver("work_item", work_item_scope)
# F-03-T22: the two kinds engagements owns; tax, closes and notices register theirs.
register_work_item_kind("assurance", AssuranceKind())
register_work_item_kind("advisory_project", AdvisoryProjectKind())
register_scope_resolver("client", client_scope)
register_scope_resolver("client_entity", client_entity_scope)
# P-08-T18: POR-01 d's names, and the contact an accepted invitation activates (organisations').
register_invitation_parties(invitation_parties)
register_contact_activation(activate_contact)
# P-08-T17 (DEC-34, DEC-63): approvers, signing officers and SKE designees need the second step.
register_mfa_requirement("engagement_designation", mfa_designated)
# T-01-T12 (C19): a grant reaching tax return information (a K-1 package, a tax return work
# item or an engagement holding one) needs the second step too.
register_mfa_requirement("tri_scope", mfa_tri_scope)
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
    # The team, acceptance and independence contract, v1 (P-07-T29).
    acceptance_router,
    independence_router,
    team_roles_router,
    # The intake and import contract, v1 (P-07-T37).
    dedupe_router,
    client_intake_drafts_router,
    client_imports_router,
    letter_router,  # C7 v1 letter half stub (N-02-T03): ENG-04 composer
    roll_forward_router,  # P-07-T55: ENG-13 v2, behind engagements.roll_forward_v2
    router,
    work_items_router,
    firm_router,
)

# P-07-T52: the bulk import's workflow, activities and daily erase make engagements a module with
# worker parts; it subscribes to nothing.
SUBSCRIPTIONS: dict[str, Callable[[OutboxEvent], Awaitable[None]]] = {}

register_pilot_metric_source("w4", w4_portal_activation)  # Q-04-T008 (DEC-825)

__all__ = [
    "ACCEPTANCE_DECISION_DUE",
    "ACTIVITIES",
    "AUDIT_KINDS",
    "EQR_ELIGIBILITY_DUE",
    "INDEPENDENCE_CONCLUSION_DUE",
    "INDEPENDENCE_CONFIRMATION_DUE",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "WORK_ITEM_FUNCTIONS",
    "AccountRule",
    "ApprovedGuidance",
    "Area",
    "AssignedWork",
    "AssuranceItem",
    "CheckFacts",
    "Designation",
    "DueGate",
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
    "MaskedTinOut",
    "MethodologyAlreadyApplied",
    "MethodologyVersionView",
    "NewCondition",
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
    "WorkItemFacts",
    "WorkItemProvider",
    "acceptance_decisions_due",
    "acceptance_record",
    "add_flag",
    "add_to_team",
    "ai_excluded",
    "all_engagement_ids",
    "answer_independence",
    "approve_eqr_eligibility",
    "approve_team",
    "archive_work_item",
    "area_for",
    "assign_eqr",
    "assign_work_item",
    "assigned_work",
    "assurance_index",
    "assurance_item",
    "assurance_item_id",
    "attach_letter_file",
    "audit_engagements",
    "change_team_role",
    "check_facts",
    "client_contact_names",
    "client_contact_organisations",
    "client_contact_organisations_of_users",
    "client_tax_years",
    "client_tri_subjects",
    "commit_client_intake",
    "complete_manual_check",
    "conclude_independence",
    "confirm_independence",
    "contact_portal_user",
    "create_draft",
    "create_work_item",
    "decide_acceptance",
    "designate_contact",
    "engagement_contacts",
    "engagement_hold_facts",
    "engagement_label",
    "engagement_metadata",
    "engagements_in_hold_scope",
    "engagements_of_entity",
    "entity_of",
    "eqr_eligibility_due",
    "firm_router",
    "g2_blocks",
    "gate_client_data",
    "gate_fact",
    "gate_offices",
    "gate_registered",
    "get_ref",
    "holds_tax_return",
    "independence_cleared",
    "independence_conclusions_due",
    "independence_confirmations_due",
    "is_archived",
    "judgments_of",
    "letters_sent",
    "lock_assurance_item",
    "lock_engagement",
    "lock_ref",
    "methodology_version",
    "open_engagements",
    "pin_methodology",
    "pin_methodology_on",
    "portal_work_items",
    "progress_of",
    "publish_drafted_version",
    "readable_client",
    "recorded_letter",
    "register_auto_retrieval",
    "register_draft_request_copy",
    "register_evidence_readable",
    "register_gate_provider",
    "register_judgment_source",
    "register_open_requests",
    "register_progress_source",
    "register_roll_forward_items",
    "register_work_item_kind",
    "remove_from_team",
    "replace_gate_provider",
    "request_manual_check",
    "require_open",
    "router",
    "run_auto_retrieval",
    "send_to_partner",
    "service_line_of",
    "set_ai_exclusion_of",
    "set_assurance_profile",
    "start_acceptance",
    "stored_file",
    "team_approval",
    "update_answers",
    "version_detail",
    "visible_among",
    "work_item_engagement",
    "work_item_facts",
    "work_item_index",
    "work_item_offices",
    "work_item_provider",
]
