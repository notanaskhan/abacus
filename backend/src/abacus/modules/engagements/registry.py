"""The engagements module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "engagements",
        # The methodology_* tables are the methodology module's since K-01-T02 (0180).
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
        "client_intake_drafts",  # P-07-T42 (0177): CLI-06's autosaved intake, own scope
        "team_approvals",  # P-07-T30 (0155): the EP's approval of the team
        "eqr_eligibility_approvals",  # P-07-T30 (0155): the quality owner's EQR approvals
        # P-07-T35 (0163): acceptance and continuance in-app (CLI-07)
        "acceptance_questionnaire_templates",
        "acceptance_questionnaire_template_versions",
        "acceptance_records",
        "acceptance_answers",
        "acceptance_manual_checks",
        "acceptance_flags",
        "acceptance_decisions",
        "acceptance_conditions",
        "acceptance_condition_events",
        "risk_partner_reviews",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "work_item_assignments",  # F-03-T05 (0068)
        "engagement_entities",  # F-03-T05 (0068)
        "gate_policy_overrides",  # F-03-T12 (0069): a new row per change
        "engagement_contacts",  # F-03-T25 (0082)
        "advisory_projects",  # F-03-T22 (0089)
        "team_approvals",  # P-07-T30 (0155)
        "eqr_eligibility_approvals",  # P-07-T30 (0155)
        # P-07-T35 (0163): firm content versions and a person's acts, never changed
        "acceptance_questionnaire_templates",
        "acceptance_questionnaire_template_versions",
        "acceptance_flags",
        "acceptance_decisions",
        "acceptance_conditions",
        "acceptance_condition_events",
        "risk_partner_reviews",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # P-07-T35 (0163): acceptance and continuance (CLI-07)
    "acceptance_questionnaire_templates": frozenset({"tenant_id", "name", "family", "created_by"}),
    "acceptance_questionnaire_template_versions": frozenset(
        {"tenant_id", "template_id", "version_no", "sections", "created_by"}
    ),
    "acceptance_records": frozenset(
        {"id", "tenant_id", "engagement_id", "client_id", "kind", "template_version_id"}
        | {"prepared_by", "prior_record_id"}
    ),
    "acceptance_answers": frozenset(
        {"tenant_id", "record_id", "section_code", "answers_sealed", "state", "updated_by"}
    ),
    "acceptance_manual_checks": frozenset(
        {"id", "tenant_id", "record_id", "section_code", "requested_of", "requested_by"}
    ),
    "acceptance_flags": frozenset(
        {"id", "tenant_id", "record_id", "severity", "title_sealed", "body_sealed"}
        | {"source_refs", "authored_by"}
    ),
    "acceptance_decisions": frozenset(
        {"id", "tenant_id", "record_id", "option", "rationale_sealed", "decided_by"}
        | {"mfa_verified_at"}
    ),
    "acceptance_conditions": frozenset(
        {"id", "tenant_id", "record_id", "decision_id", "position", "text_sealed"}
        | {"assignee_user_id", "due_on"}
    ),
    "acceptance_condition_events": frozenset(
        {"id", "tenant_id", "condition_id", "note_sealed", "actor_id"}
    ),
    "risk_partner_reviews": frozenset(
        {"tenant_id", "record_id", "event", "partner_id", "actor_id"}
    ),
    "team_approvals": frozenset(  # P-07-T30 (0155)
        {"tenant_id", "engagement_id", "approved_by", "member_set_hash"}
    ),
    "eqr_eligibility_approvals": frozenset(  # P-07-T30 (0155)
        {"tenant_id", "engagement_id", "candidate_user_id", "checks", "result", "approved_by"}
    ),
    "advisory_projects": frozenset({"tenant_id", "work_item_id", "engagement_id", "name"}),
    "engagement_contacts": frozenset(  # F-03-T25 (0082)
        {"tenant_id", "engagement_id", "contact_id", "designation", "designated_by"}
    ),
    "engagement_drafts": frozenset(  # P-07-T16 (0124)
        {"tenant_id", "created_by", "client_id", "client_entity_id", "type_code", "step"}
        | {"payload"}
    ),
    "client_intake_drafts": frozenset(  # P-07-T42 (0177)
        {"tenant_id", "created_by", "step", "payload"}
    ),
    "engagements": frozenset(
        {"id", "tenant_id", "client_id", "client_entity_id", "name", "created_by"}
        | {"fiscal_period_start", "fiscal_period_end"}
        | {"type"}  # SPEC-024: the engagement's type
        | {"prior_engagement_id"}  # SPEC-025 (TASK-048): roll-forward, set at creation only
        | {"office_id", "standards_set_id"}  # F-03-T12 (0069)
    ),
    # The methodology_* tables' columns are the methodology module's since K-01-T02 (0180).
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
    # P-07-T35 (0163): a guard trigger refuses any change once the record is decided.
    "acceptance_records": frozenset(
        {"status", "risk_rating", "sent_to_partner_at", "sent_to_partner_by", "version"}
    ),
    "acceptance_answers": frozenset(
        {"answers_sealed", "state", "version", "updated_by", "updated_at"}
    ),
    "acceptance_manual_checks": frozenset({"completed_by", "note_sealed"}),
    "engagements": frozenset(
        {"status", "methodology_version_id"}  # SPEC-008: pinned once
        | {"ai_excluded_at", "ai_excluded_by", "ai_excluded_reason"}  # SPEC-036 (TASK-076)
        | {"period_label"}  # P-07-T15 (0124); `version` is the trigger's, never the app's
        | {"hold_reason"}  # TASK-1198 (0155): set and cleared with the hold
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
    "client_intake_drafts": frozenset(  # P-07-T42 (0177): autosave, discard, commit
        {"step", "payload", "version", "saved_at", "discarded_at", "committed_at"}
        | {"committed_client_id", "result"}
    ),
}
