"""The engagements module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "engagements",
        "methodology_templates",
        "methodology_versions",
        "methodology_areas",
        "methodology_request_items",
        "methodology_account_rules",
        "engagement_acceptance",
        "independence_confirmations",
        "work_items",  # F-03-T05 (0068)
        "assurance_work_items",
        "work_item_assignments",
        "engagement_entities",
        "gate_policy_overrides",  # F-03-T12 (0069)
        "engagement_letters",
        "engagement_contacts",  # F-03-T25 (0082): designations (DEC-63)
        "advisory_projects",  # F-03-T22 (0089)
        "engagement_drafts",  # P-07-T16 (0124): ENG-03's autosaved wizard, own scope
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "methodology_templates",
        "methodology_versions",
        "methodology_areas",
        "methodology_request_items",
        "methodology_account_rules",
        "work_item_assignments",  # F-03-T05 (0068)
        "engagement_entities",  # F-03-T05 (0068)
        "gate_policy_overrides",  # F-03-T12 (0069): a new row per change
        "engagement_contacts",  # F-03-T25 (0082)
        "advisory_projects",  # F-03-T22 (0089)
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "advisory_projects": frozenset({"tenant_id", "work_item_id", "engagement_id", "name"}),
    "engagement_contacts": frozenset(  # F-03-T25 (0082)
        {"tenant_id", "engagement_id", "contact_id", "designation", "designated_by"}
    ),
    "engagement_drafts": frozenset(  # P-07-T16 (0124)
        {"tenant_id", "created_by", "client_id", "client_entity_id", "type_code", "step"}
        | {"payload"}
    ),
    "engagements": frozenset(
        {"id", "tenant_id", "client_id", "client_entity_id", "name", "created_by"}
        | {"fiscal_period_start", "fiscal_period_end"}
        | {"type"}  # SPEC-024: the engagement's type
        | {"prior_engagement_id"}  # SPEC-025 (TASK-048): roll-forward, set at creation only
        | {"office_id", "standards_set_id"}  # F-03-T12 (0069)
    ),
    # Methodology templates (SPEC-008): insert-only, immutable versions.
    "methodology_templates": frozenset(
        {"id", "tenant_id", "name", "created_by", "engagement_types"}  # SPEC-024: types served
    ),
    "methodology_versions": frozenset(
        {"id", "tenant_id", "template_id", "version", "source_fingerprint", "imported_by"}
    ),
    "methodology_areas": frozenset({"tenant_id", "version_id", "code", "name", "position"}),
    "methodology_request_items": frozenset(
        {"tenant_id", "version_id", "area_code", "description", "retrievability_tier"}
        | {"position"}
        | {"why", "good_looks_like", "blocks_fieldwork", "effort"}  # SPEC-031 (TASK-060)
        | {"guidance_source", "guidance_approved_by"}  # SPEC-035 Q3 (TASK-074)
    ),
    "methodology_account_rules": frozenset(
        {"tenant_id", "version_id", "area_code", "account_from", "account_to", "position"}
    ),
    # Work items (F-03-T05; migration 0068).
    "work_items": frozenset(
        {"tenant_id", "engagement_id", "client_id", "client_entity_id", "kind", "name"}
        | {"period_start", "period_end", "office_id", "due_on", "created_by"}
    ),
    "assurance_work_items": frozenset(
        {"work_item_id", "tenant_id", "engagement_id", "assurance_type", "phase", "is_group_audit"}
    ),
    "work_item_assignments": frozenset(
        {"tenant_id", "work_item_id", "engagement_id", "user_id", "function", "assigned_by"}
        | {"removed_at"}
    ),
    "engagement_entities": frozenset(
        {"tenant_id", "engagement_id", "client_entity_id", "role", "ownership_pct"}
    ),
    "gate_policy_overrides": frozenset(  # F-03-T12 (0069)
        {"tenant_id", "type_family", "gate", "requirement", "set_by"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "engagements": frozenset(
        {"status", "methodology_version_id"}  # SPEC-008: pinned once
        | {"ai_excluded_at", "ai_excluded_by", "ai_excluded_reason"}  # SPEC-036 (TASK-076)
        | {"period_label"}  # P-07-T15 (0124); `version` is the trigger's, never the app's
    ),
    # SPEC-025 (TASK-044): a person answers once; the letter's record is replaced in place.
    "independence_confirmations": frozenset(
        {"status", "statement_version", "note", "answered_at"}
    ),
    "work_items": frozenset({"name", "status", "due_on", "archived_at", "archive_locked_at"}),
    # F-03-T05 (0068) granted phase and auto_mode; A-01-T05 (0134) adds the EBP profile facts and
    # the version, and takes `phase` away: it moves only through an assurance phase event, whose
    # SECURITY DEFINER trigger writes phase, phase_source and phase_changed_at (DEC-262).
    "assurance_work_items": frozenset(
        {"auto_mode", "ebp_plan_kind", "limited_scope_103a3c", "standards_set_id", "version"}
    ),
    "engagement_letters": frozenset(
        {"status", "letter_date", "reason", "link", "recorded_by", "recorded_at"}
        | {"file_key", "file_version_id", "file_fingerprint", "file_size", "file_media_type"}
        | {"file_name"}
        # P-07-T15 (0124): the interim recorded letter (G3 until C7)
        | {"client_signed_on", "firm_signed_on", "client_signer_contact_id"}
        | {"firm_signer_user_id", "signed_copy_version_id", "recorded_by_user_id"}
    ),
    "engagement_drafts": frozenset(  # P-07-T16 (0124): autosave, discard, create
        {"client_id", "client_entity_id", "type_code", "step", "payload"}
        | {"prospect_engagement_id", "created_engagement_id", "version", "saved_at"}
        | {"discarded_at"}
    ),
}
