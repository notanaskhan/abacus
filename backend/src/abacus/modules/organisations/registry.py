"""The organisations module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "clients",
        "client_entities",
        # F-03-T23 (DEC-30): offices are a filter, never an access boundary (Q-21).
        "offices",
        "teams",
        "team_rosters",
        "contacts",  # F-03-T25 (0082)
        "entity_relationships",  # P-07-T07 (0103): ended, never deleted
        "tin_reveals",  # P-07-T10 (0123): every logged TIN reveal, by a person
        "contact_roles",  # P-07-T25 (0146): roles per entity, replaced as a set
        "contact_group_members",  # P-07-T25 (0146)
        # P-07-T36 (0164): conflict checks and screening, insert-only
        "conflict_checks",
        "conflict_results",
        "conflict_result_events",
        "screening_records",
        # T-01-T08 (0402): §7216 consents, their signers and events.
        "consent_sets",
        "consents",
        "consent_signers",
        "consent_events",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {"tin_reveals", "team_rosters"}  # rosters: 0150
    | {"conflict_checks", "conflict_results", "conflict_result_events", "screening_records"}
    | {"consent_sets", "consent_events"}  # T-01-T08 (0402)
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # P-07-T36 (0164): names and reasons sealed; matched names never stored
    "conflict_checks": frozenset(
        {"id", "tenant_id", "subject_kind", "subject_id", "names_sealed", "names_count"}
        | {"status", "run_by"}
    ),
    "conflict_results": frozenset(
        {"tenant_id", "check_id", "name_index", "matched_ref_type", "matched_ref_id"}
        | {"matched_client_id", "match_kind", "score", "counterparty_role"}
    ),
    "conflict_result_events": frozenset(
        {"id", "tenant_id", "result_id", "assessment", "reason_sealed", "cleared_by"}
    ),
    "screening_records": frozenset(
        {"id", "tenant_id", "subject_kind", "subject_id", "list", "result"}
        | {"evidence_version_id", "note_sealed", "recorded_by"}
    ),
    "clients": frozenset({"id", "tenant_id", "name"}),
    "client_entities": frozenset({"id", "tenant_id", "client_id", "name"}),
    "offices": frozenset(
        {"tenant_id", "name", "time_zone"}
        # G-01-T08 (0150): ADM-03a's office facts
        | {"code", "is_hq", "address_line1", "address_line2", "city", "region_code"}
        | {"postal_code", "lead_user_id", "default_reviewer_pool_team_id"}
    ),
    "teams": frozenset(
        {"tenant_id", "office_id", "name"} | {"kind", "service_line", "lead_user_id"}  # 0150
    ),
    "team_rosters": frozenset(
        {"tenant_id", "team_id", "user_id"} | {"removed_at"}  # 0150: history
    ),
    "contacts": frozenset(  # F-03-T25 (0082)
        {"id", "tenant_id", "client_id", "display_name", "email", "phone", "title"}
        | {"organisation_name", "contact_kind"}
        | {"party_kind"}  # P-07-T25 (0146)
    ),
    "contact_roles": frozenset(  # P-07-T25 (0146)
        {"tenant_id", "contact_id", "scope_kind", "scope_id", "role", "title_text"}
    ),
    "contact_group_members": frozenset(  # P-07-T25 (0146)
        {"tenant_id", "group_contact_id", "member_contact_id"}
    ),
    "entity_relationships": frozenset(  # P-07-T07 (0103)
        {"tenant_id", "from_entity_id", "to_entity_id", "kind", "percent", "effective_from"}
        | {"effective_to", "created_by"}
    ),
    "tin_reveals": frozenset(  # P-07-T10 (0123): never the value
        {"tenant_id", "client_entity_id", "engagement_id", "user_id", "reason_code", "mfa_at"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
# T-01-T08 (0402): consents and their signers, set at insert; events append only.
INSERT_COLUMNS["consent_sets"] = frozenset(
    {"id", "tenant_id", "client_id", "filing_unit_entity_id", "kind", "tax_years", "created_by"}
)
INSERT_COLUMNS["consents"] = frozenset(
    {"id", "tenant_id", "client_id", "client_entity_id", "consent_set_id", "purpose"}
    | {"tax_years", "scope", "recipients", "provider_terms_version", "template_version_id"}
    | {"text_sha256", "source", "envelope_id", "status", "requested_at", "renewal_of_id"}
    | {"created_by", "signed_at", "declined_at", "expires_at"}  # record mode carries its dates
)
INSERT_COLUMNS["consent_signers"] = frozenset(
    {"id", "tenant_id", "consent_id", "contact_id", "user_id", "signer_role", "required"}
)
INSERT_COLUMNS["consent_events"] = frozenset(
    {"tenant_id", "consent_id", "kind", "actor_kind", "actor_id", "facts"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # T-01-T08 (0402): a consent's lifecycle and a signer's signature; never deleted.
    "consents": frozenset(
        {"status", "signed_at", "expires_at", "declined_at", "revoked_at", "copy_delivered_at"}
        | {"copy_delivered_channel", "row_version"}
    ),
    "consent_signers": frozenset({"signed_at", "method", "evidence_version_id"}),
    # G-01-T08 (0150): offices and teams are edited in place, versioned; never deleted.
    "offices": frozenset(
        {"name", "time_zone", "code", "is_hq", "address_line1", "address_line2", "city"}
        | {"region_code", "postal_code", "lead_user_id", "default_reviewer_pool_team_id"}
        | {"version"}
    ),
    "teams": frozenset({"name", "kind", "service_line", "office_id", "lead_user_id", "version"}),
    # F-03-T25 (0082): the client record (DEC-62). `is_attest_client` is the database's to
    # derive (DEC-128), never the app's.
    "clients": frozenset(
        {"kind", "status", "primary_office_id", "relationship_partner_id", "risk_tier"}
        | {"portal_status", "practice_mgmt_ref"}
        | {"descriptor"}  # P-07-T07
    ),
    "client_entities": frozenset(
        {"entity_type", "fye_month_day", "state_of_formation", "plan_number", "date_of_death"}
        | {"grantor_status"}
        # P-07-T07 (DEC-52): sealed under the firm's key; written only by P-07-T10's sealing.
        | {"tin_sealed", "tin_last4", "tin_kind", "tin_status", "tin_fingerprint"}
    ),
    "contacts": frozenset(
        {"display_name", "phone", "title", "organisation_name", "user_id", "portal_state"}
        | {"email", "party_kind", "version"}  # P-07-T25 (0146): the drawer's edit
    ),
    "entity_relationships": frozenset({"effective_to"}),  # P-07-T07: a relationship ends
}
