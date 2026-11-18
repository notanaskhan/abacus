"""The engagements module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
_TABLES_PRE_S50: frozenset[str] = frozenset(
    {
        "engagements",
        # The methodology_* tables are the methodology module's since K-01-T02 (0180).
        "independence_confirmations",
        "work_items",  # F-03-T05 (0068)
        "assurance_work_items",
        "work_item_assignments",
        "engagement_entities",
        "gate_policy_overrides",  # F-03-T12 (0069)
        "engagement_letters",
        "engagement_letter_versions",  # N-02-T32 (0560): composed versions, content fixed
        "engagement_contacts",  # F-03-T25 (0082): designations (DEC-63)
        "advisory_projects",  # F-03-T22 (0089)
        "engagement_drafts",  # P-07-T16 (0124): ENG-03's autosaved wizard, own scope
        "client_intake_drafts",  # P-07-T42 (0177): CLI-06's autosaved intake, own scope
        "client_imports",  # P-07-T52 (0250): CLI-06's bulk import, its sealed file 30 days
        "client_import_rows",  # P-07-T52 (0250): parsed rows, decisions, what the run applied
        "roll_forward_drafts",  # P-07-T55 (0291): ENG-13's saved wizard, own scope
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
        # P-07-T41 (0175): independence in-app (CLI-08)
        "independence_conclusions",
        "nas_evaluations",
        "nas_evaluation_events",
        "independence_breaches",
        "independence_breach_events",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
_INSERT_ONLY_PRE_S50: frozenset[str] = frozenset(
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
        # P-07-T41 (0175): a person's conclusion, evaluations and the breach log
        "independence_conclusions",
        "nas_evaluations",
        "nas_evaluation_events",
        "independence_breaches",
        "independence_breach_events",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # N-02-T32 (0560): a composed letter's version; only the lifecycle columns change after
    "engagement_letter_versions": frozenset(
        {"id", "tenant_id", "engagement_id", "version_no", "kind", "amends_version_id"}
        | {"template_version_id", "clause_states", "variables", "section_overrides", "fee_terms"}
        | {"generated_document_id", "content_hash", "status", "created_by", "created_by_kind"}
    ),
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
    # P-07-T41 (0175): independence in-app (CLI-08)
    "independence_conclusions": frozenset(
        {"id", "tenant_id", "engagement_id", "option", "safeguards_sealed", "concluded_by"}
        | {"mfa_verified_at", "supersedes_id"}
    ),
    "nas_evaluations": frozenset(
        {"id", "tenant_id", "engagement_id", "service_code", "created_by"}
    ),
    "nas_evaluation_events": frozenset(
        {"id", "tenant_id", "nas_id", "provided", "status", "evaluation_sealed"}
        | {"safeguards_sealed", "ske_contact_id", "recorded_by"}
    ),
    "independence_breaches": frozenset(
        {"id", "tenant_id", "engagement_id", "description_sealed", "user_id", "logged_by"}
    ),
    "independence_breach_events": frozenset(
        {"id", "tenant_id", "breach_id", "kind", "note_sealed", "recorded_by"}
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
    "client_imports": frozenset(  # P-07-T52 (0250)
        {"id", "tenant_id", "source", "file_name", "file_sealed", "file_sha256", "file_bytes"}
        | {"stage", "mapping", "counts", "started_by"}
    ),
    "client_import_rows": frozenset(  # P-07-T52 (0250)
        {"id", "tenant_id", "import_id", "row_no", "parsed", "tin_sealed", "tin_kind"}
        | {"tin_last4", "tin_fingerprint", "best_match_client_id", "best_match_entity_id"}
        | {"score", "basis", "decision", "error_code"}
    ),
    "roll_forward_drafts": frozenset(  # P-07-T55 (0291)
        {"tenant_id", "source_engagement_id", "created_by", "target_period_start"}
        | {"target_period_end", "name", "selections", "team", "template_decision"}
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
        # P-07-T41 (0175): the statements ticked, sealed notes and reminders
        | {"statements", "interests_note", "decline_note", "reminder_count", "last_reminded_at"}
    ),
    "work_items": frozenset({"name", "status", "due_on", "archived_at", "archive_locked_at"}),
    # F-03-T05 (0068) granted phase and auto_mode; A-01-T05 (0134) adds the EBP profile facts and
    # the version, and takes `phase` away: it moves only through an assurance phase event, whose
    # SECURITY DEFINER trigger writes phase, phase_source and phase_changed_at (DEC-262).
    "assurance_work_items": frozenset(
        {"auto_mode", "ebp_plan_kind", "limited_scope_103a3c", "standards_set_id", "version"}
        | {"is_group_audit"}  # A-09-T30 (0946, DEC-5408): ENG-03 g's group toggle
    ),
    "engagement_letters": frozenset(
        {"status", "letter_date", "reason", "link", "recorded_by", "recorded_at"}
        | {"file_key", "file_version_id", "file_fingerprint", "file_size", "file_media_type"}
        | {"file_name"}
        # P-07-T15 (0124): the interim recorded letter (G3 until C7)
        | {"client_signed_on", "firm_signed_on", "client_signer_contact_id"}
        | {"firm_signer_user_id", "signed_copy_version_id", "recorded_by_user_id"}
        # N-02-T32 (0560): the composed letter
        | {"current_version_id", "mode", "envelope_id"}
    ),
    # N-02-T32 (0560): the lifecycle, forward only (the guard trigger); content never changes
    "engagement_letter_versions": frozenset(
        {"status", "approved_by", "approved_at", "approval_content_hash", "envelope_id"}
        | {"approval_requested_at", "approval_requested_by", "final_document_version_id"}  # 0563
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
    # P-07-T52 (0250): the run's claim and end; a person's decision, what the run applied. The
    # 30-day erase is `client_import_files_erase()`'s, never the app's.
    "client_imports": frozenset({"stage", "counts", "run_by", "run_at", "completed_at"}),
    "client_import_rows": frozenset(
        {"decision", "merge_client_id", "decided_by", "decided_at", "applied_at", "result_ref"}
        | {"error_code"}
    ),
    "roll_forward_drafts": frozenset(  # P-07-T55 (0291): autosave, discard, create
        {"target_period_start", "target_period_end", "name", "selections", "team"}
        | {"template_decision", "created_engagement_id", "version", "saved_at", "discarded_at"}
    ),
}

# T-08-T05 (0960, DEC-5604).
T08T05_TABLES: frozenset[str] = frozenset(
    {
        "season_asks",
        "season_cohort_approvals",
        "season_cohort_withdrawals",
        "season_cohorts",
        "season_manifest_rows",
        "season_manifests",
        "season_row_steps",
        "seasons",
    }
)
_S50_INSERT_ONLY_1: frozenset[str] = frozenset(
    {
        "season_cohort_approvals",
        "season_cohort_withdrawals",
        "season_row_steps",
    }
)
INSERT_COLUMNS["seasons"] = frozenset(
    {
        "opened_by",
        "tax_year",
        "tenant_id",
    }
)
INSERT_COLUMNS["season_manifests"] = frozenset(
    {
        "built_by",
        "inputs_hash",
        "planner_run_id",
        "season_id",
        "status",
        "tenant_id",
        "version",
    }
)
UPDATE_COLUMNS["season_manifests"] = frozenset(
    {
        "planner_run_id",
        "status",
    }
)
INSERT_COLUMNS["season_cohorts"] = frozenset(
    {
        "approver_user_id",
        "manifest_id",
        "office_id",
        "position",
        "segment",
        "tenant_id",
    }
)
UPDATE_COLUMNS["season_cohorts"] = frozenset(
    {
        "approver_user_id",
        "status",
    }
)
INSERT_COLUMNS["season_manifest_rows"] = frozenset(
    {
        "binder_source",
        "client_entity_ids",
        "client_id",
        "cohort_id",
        "consent_purposes",
        "exception_codes",
        "forms",
        "invitee_contact_ids",
        "letter_plan",
        "preparer_user_id",
        "prior_engagement_id",
        "reviewer_user_id",
        "signer_user_id",
        "tenant_id",
    }
)
UPDATE_COLUMNS["season_manifest_rows"] = frozenset(
    {
        "exception_codes",
        "excluded_at",
        "excluded_by",
        "exclusion_reason",
        "preparer_user_id",
        "reviewer_user_id",
        "row_version",
        "signer_user_id",
    }
)
INSERT_COLUMNS["season_asks"] = frozenset(
    {
        "manifest_id",
        "options",
        "question_code",
        "recommended_option",
        "row_ids",
        "source",
        "suggestion_id",
        "tenant_id",
    }
)
UPDATE_COLUMNS["season_asks"] = frozenset(
    {
        "answered_at",
        "answered_by",
        "answered_option",
    }
)
INSERT_COLUMNS["season_cohort_approvals"] = frozenset(
    {
        "approval_grant_id",
        "approved_by",
        "cohort_id",
        "manifest_version",
        "rows_hash",
        "tenant_id",
    }
)
INSERT_COLUMNS["season_cohort_withdrawals"] = frozenset(
    {
        "approval_id",
        "reason",
        "tenant_id",
        "withdrawn_by",
    }
)
INSERT_COLUMNS["season_row_steps"] = frozenset(
    {
        "attempt",
        "error_code",
        "ref_ids",
        "row_id",
        "status",
        "step",
        "tenant_id",
    }
)

# The tables this module owns and its insert-only tables, after S50 (one definition each).
TABLES: frozenset[str] = _TABLES_PRE_S50 | T08T05_TABLES
INSERT_ONLY: frozenset[str] = _INSERT_ONLY_PRE_S50 | _S50_INSERT_ONLY_1
