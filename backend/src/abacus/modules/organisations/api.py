"""Public interface of the organisations module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_client_owners
from abacus.kernel.dispatch import WorkClass, register_work_classes
from abacus.kernel.uow.placement import register_client_placer
from abacus.modules.identity.api import (
    AbacusRouter,
    register_client_partner,
    register_intake_scope,
    register_member_teams,
    register_office_list,
    register_settings_area,
)
from abacus.modules.organisations.activities import ACTIVITIES as CONSENT_ACTIVITIES
from abacus.modules.organisations.activities import SCHEDULES as CONSENT_SCHEDULES
from abacus.modules.organisations.audit_placement import client_offices
from abacus.modules.organisations.audit_targets import CLIENT_KINDS, audit_clients
from abacus.modules.organisations.conflicts import (
    check_clear_for,
    clear_conflict_result,
    run_conflict_check,
    standing_conflict_results,
)
from abacus.modules.organisations.conflicts_contract import (
    conflict_checks_router,
    screening_records_router,
)
from abacus.modules.organisations.consent_gate import (
    TriConsentRequired,
    TriSubject,
    consent_counts,
    consent_state,
    covering_consents,
    register_consent_gate,
    require_tri_consent,
    tri_consent_verdict,
)
from abacus.modules.organisations.consents import (
    ConsentDraft,
    FilingUnit,
    check_scope,
    consent_template_versions_on,
    envelope_completed,
    filing_unit,
    record_request,
    record_signed,
    refuse_declined,
    renewal_basis,
)
from abacus.modules.organisations.consents_contract import (
    AgreeingFormOut,
    AuthorizationForm,
    AuthorizationStatus,
    ConsentDraftsOut,
    ConsentRecordIn,
    ConsentRenewalIn,
    ConsentRequestIn,
    ConsentState,
    TaxAuthorizationDesigneeOut,
    TaxAuthorizationIn,
    TaxAuthorizationOut,
    TaxElectionIn,
    TaxElectionOut,
    TaxProfileFileOut,
    TranscriptComparisonIn,
    TranscriptComparisonOut,
    TranscriptLineDiffOut,
    TranscriptOut,
    TranscriptTransactionOut,
    TranscriptUploadIn,
    TriVerdict,
    consent_outs,
    consents_router,
)
from abacus.modules.organisations.contacts import RoleAsked, contact_portal_facts, create_contact
from abacus.modules.organisations.contacts_contract import (
    client_contacts_router,
    contact_invitations_router,
    contacts_router,
)
from abacus.modules.organisations.contract import (
    MaskedTinOut,
    client_entities_router,
    clients_router,
)

# P-07-T42 (DEC-430, DEC-441): what CLI-06's single intake reads and writes here.
from abacus.modules.organisations.intake import (
    CONTACT_ROLES,
    ENTITY_TYPES,
    RELATIONSHIP_KINDS,
    DedupeMatch,
    add_intake_contact,
    add_intake_relationship,
    dedupe_candidates,
    ein_matches,
    same_name_client,
)
from abacus.modules.organisations.intake_team import on_intake_team
from abacus.modules.organisations.live import (
    NewRelationship,
    add_relationship,
    contacts_section,
    entities_section,
    key_dates_section,
    readable_client,
)
from abacus.modules.organisations.plan_numbers import (
    entity_name,
    entity_plan_number,
    set_entity_plan_number,
)

# P-06-T11: correlated name columns for another module's list (BND-01's client and office).
from abacus.modules.organisations.repository import (
    client_name_column,
    entity_name_column,
    office_name_column,
)
from abacus.modules.organisations.rosters import member_teams, service_line_teams, set_member_teams
from abacus.modules.organisations.service import (
    ClientChoice,
    ClientNames,
    ClientRecord,
    ClientRecordChange,
    ClientRecordInvalid,
    ContactExists,
    ContactFacts,
    ContactKind,
    ContactLinked,
    ContactView,
    EntityAttributes,
    EntityChoice,
    FirmName,
    NewClient,
    NewContact,
    SignerContact,
    activate_contact,
    add_contact,
    attest_client_ids,
    attest_client_of,
    client_exists,
    client_names,
    client_of_entity,
    client_partner_of,
    client_record,
    client_with_entity,
    contact_client,
    contact_facts,
    contacts_of_user,
    create_client,
    entity_display_name,
    entity_tin_last4s,
    find_clients,
    firm_names,
    firm_offices,
    normalise,
    portal_activation,
    set_client_record,
    set_entity_attributes,
    signer_contacts,
)
from abacus.modules.organisations.settings_contract import offices_glance, org_settings_router
from abacus.modules.organisations.slots import (
    OverviewItem,
    OverviewSection,
    SectionRows,
    SubjectNames,
    register_client_engagements,
    register_conflict_subject,
    register_conflict_subject_names,
    register_consent_capture,
    register_office_facts,
    register_open_requests,
    register_overview_section,
    register_screening_evidence,
)

# T-01-T43: the tax-profile family's live routes register on `consents_router` at import.
from abacus.modules.organisations.tax_profile import (
    TaxProfileBackend,
    register_tax_profile_backend,
)
from abacus.modules.organisations.tin import (
    MaskedTin,
    TinConflict,
    TinInvalid,
    TinKindNotAllowed,
    clear_tin,
    fingerprint_tin,
    mask_tin,
    seal_tin,
)
from abacus.modules.organisations.workflows import (
    ConsentExportWorkflow,
    ConsentLifecycleSweepWorkflow,
)

# The routers the API mounts, in order (P-39; F-03-T07).
# T-01-T16: the consent export and the daily lifecycle sweep (background work).
WORKFLOWS: dict[type, WorkClass] = {
    ConsentExportWorkflow: "background",
    ConsentLifecycleSweepWorkflow: "background",
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = CONSENT_ACTIVITIES
SCHEDULES = CONSENT_SCHEDULES

ROUTERS: tuple[AbacusRouter, ...] = (
    clients_router,  # the clients family contract, v1 stub (P-07-T04)
    client_entities_router,
    client_contacts_router,  # contacts and portal access, v1 stub (P-07-T17)
    contacts_router,
    contact_invitations_router,
    conflict_checks_router,  # conflict checks and screening, v1 stub (P-07-T29)
    screening_records_router,
    org_settings_router,  # firm-settings family v1: offices and teams (G-01-T02 stub)
    consents_router,  # C19 v1: consents, the TRI gate and the tax profile (T-01-T01 stub)
)

# P-01-T04: identity's `/v1/me` lists the firm's offices through this.
register_office_list(firm_offices)
# G-02-T08 gap (DEC-458): a client's primary office for its audit events.
register_client_placer(client_offices)
# T-01-T10, T-01-T16: a consent event belongs to its client (the explorer hides walled ones).
register_client_owners(CLIENT_KINDS, audit_clients)
# G-01-T05: ADM-02 reads and replaces a person's teams through this; G-01-T08: and the
# service lines their service-line teams hold.
register_member_teams(member_teams, set_member_teams, service_line_teams)  # T08: AC7.4
# N-01-T08 (DEC-20, DEC-819): the intake scope is a team of kind `intake`.
register_intake_scope(on_intake_team)
# G-01-T09 (AC8.3): a wall on a client's relationship partner is refused.
register_client_partner(client_partner_of)
# G-01-T04: the Offices & teams row of the settings overview's At a glance.
register_settings_area("offices_teams", 20, offices_glance)
# P-07-T09: CLI-02's overview sections organisations owns (metadata; `client.read`).
for _section in (
    OverviewSection("entities", "details", "client.read", 10, entities_section),
    OverviewSection("key_dates", "key_dates", "client.read", 30, key_dates_section),
    OverviewSection("contacts", "table", "client.read", 40, contacts_section),
):
    register_overview_section(_section)
# T-01-T11 (C19 condition 6): the `use` and `ai_disclosure` consent checks the matrix's
# `consent(<purpose>)` reads, and the AI gateway's TRI check.
register_consent_gate()

__all__ = [
    "ACTIVITIES",
    "CONTACT_ROLES",
    "ENTITY_TYPES",
    "RELATIONSHIP_KINDS",
    "ROUTERS",
    "SCHEDULES",
    "WORKFLOWS",
    "AgreeingFormOut",
    "AuthorizationForm",
    "AuthorizationStatus",
    "ClientChoice",
    "ClientNames",
    "ClientRecord",
    "ClientRecordChange",
    "ClientRecordInvalid",
    "ConsentDraft",
    "ConsentDraftsOut",
    "ConsentRecordIn",
    "ConsentRenewalIn",
    "ConsentRequestIn",
    "ConsentState",
    "ContactExists",
    "ContactFacts",
    "ContactKind",
    "ContactLinked",
    "ContactView",
    "DedupeMatch",
    "EntityAttributes",
    "EntityChoice",
    "FilingUnit",
    "FirmName",
    "MaskedTin",
    "MaskedTinOut",
    "NewClient",
    "NewContact",
    "NewRelationship",
    "OverviewItem",
    "OverviewSection",
    "RoleAsked",
    "SectionRows",
    "SignerContact",
    "SubjectNames",
    "TaxAuthorizationDesigneeOut",
    "TaxAuthorizationIn",
    "TaxAuthorizationOut",
    "TaxElectionIn",
    "TaxElectionOut",
    "TaxProfileBackend",
    "TaxProfileFileOut",
    "TinConflict",
    "TinInvalid",
    "TinKindNotAllowed",
    "TranscriptComparisonIn",
    "TranscriptComparisonOut",
    "TranscriptLineDiffOut",
    "TranscriptOut",
    "TranscriptTransactionOut",
    "TranscriptUploadIn",
    "TriConsentRequired",
    "TriSubject",
    "TriVerdict",
    "activate_contact",
    "add_contact",
    "add_intake_contact",
    "add_intake_relationship",
    "add_relationship",
    "attest_client_ids",
    "attest_client_of",
    "check_clear_for",
    "check_scope",
    "clear_conflict_result",
    "clear_tin",
    "client_exists",
    "client_name_column",
    "client_names",
    "client_of_entity",
    "client_record",
    "client_with_entity",
    "consent_counts",
    "consent_outs",
    "consent_state",
    "consent_template_versions_on",
    "contact_client",
    "contact_facts",
    "contact_portal_facts",
    "contacts_of_user",
    "covering_consents",
    "create_client",
    "create_contact",
    "dedupe_candidates",
    "ein_matches",
    "entity_display_name",
    "entity_name",
    "entity_name_column",
    "entity_plan_number",
    "entity_tin_last4s",
    "envelope_completed",
    "filing_unit",
    "find_clients",
    "fingerprint_tin",
    "firm_names",
    "mask_tin",
    "normalise",
    "office_name_column",
    "portal_activation",
    "readable_client",
    "record_request",
    "record_signed",
    "refuse_declined",
    "register_client_engagements",
    "register_conflict_subject",
    "register_conflict_subject_names",
    "register_consent_capture",
    "register_office_facts",
    "register_open_requests",
    "register_overview_section",
    "register_screening_evidence",
    "register_tax_profile_backend",
    "renewal_basis",
    "require_tri_consent",
    "run_conflict_check",
    "same_name_client",
    "seal_tin",
    "set_client_record",
    "set_entity_attributes",
    "set_entity_plan_number",
    "signer_contacts",
    "standing_conflict_results",
    "tri_consent_verdict",
]
