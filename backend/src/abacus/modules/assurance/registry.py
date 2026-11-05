"""The assurance module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-314 (TASK-332): completion, release and archive, all insert-only and human-only.
# A-01-T05 (0134): the record-mode phase events, insert-only and human-only when recorded.
# A-01-T23 (0226): the external release and archive records, insert-only and human-only.
_HUMAN_RECORDS: frozenset[str] = frozenset(
    {"eqr_concurrences", "completion_records", "releases", "assurance_phase_events"}
    | {"assurance_external_releases", "assurance_external_archives"}
)
# A-05-T06 (0610, DEC-1861): the EBP plan audit's first tables; checks and conflicts insert-only.
EBP_TABLES: frozenset[str] = frozenset(
    {"ebp_plans", "ebp_service_providers", "ebp_provider_checks", "ebp_provisions"}
    | {"ebp_provision_conflicts"}
    | {"ebp_plan_reviews"}  # A-05-T16 (0653, DEC-2069)
)
# A-04-T06 (0613, DEC-1866): the planning record; versions and minutes approvals insert-only.
PLANNING_TABLES: frozenset[str] = frozenset(
    {"materiality_versions", "risk_register_rows", "risk_linkages", "service_organizations"}
    | {"fraud_brainstorm_sessions", "fraud_minutes_approvals", "fraud_inquiries"}
)
# A-05-T15 (0642, DEC-1959): the census and its population queries; queries insert-only.
EBP_PARTICIPANT_TABLES: frozenset[str] = frozenset(
    {"ebp_source_imports", "ebp_participants", "ebp_population_queries"}
)
# A-06-T04 (0644, DEC-1963): the completion records beside SPEC-043's (DEC-1960).
COMPLETION_TABLES: frozenset[str] = frozenset(
    {"audit_findings", "deficiencies", "audit_misstatements", "sum_snapshots", "consultations"}
)
# A-04-T25 (0657, DEC-2206): internal control and SOC 1; walkthroughs insert-only.
CONTROL_TABLES: frozenset[str] = frozenset(
    {"control_activities", "walkthroughs", "control_exceptions"}
    | {"soc_report_evaluations", "soc_exceptions", "cuecs"}
)
# A-05-T26 (0658, DEC-2207): EBP contributions; events insert-only.
EBP_CONTRIBUTION_TABLES: frozenset[str] = frozenset(
    {"ebp_payrolls", "ebp_late_remittances", "ebp_late_remittance_events"}
)
# A-07-T07 (0664, DEC-2232): EQR and completion; subsequent events insert-only.
A07_COMPLETION_TABLES: frozenset[str] = frozenset(
    {"eqr_reviews", "eqr_checklist_items", "eqr_digest_cards", "completion_items"}
    | {"subsequent_event_procedures", "subsequent_events", "legal_letters"}
    | {"going_concern_evaluations", "filings"}
)
# A-05-T35 (0665, DEC-2234): EBP investments and Form 5500; evaluations and mappings insert-only.
EBP_INVESTMENT_TABLES: frozenset[str] = frozenset(
    {"ebp_trust_report_lines", "ebp_certification_points", "ebp_certification_evaluations"}
    | {"ebp_form5500_drafts", "ebp_form5500_lines", "ebp_part_iv_answers"}
    | {"ebp_supplemental_schedules", "ebp_schedule_h_mappings"}
)
# A-05-T41 (0667, DEC-2301): EBP loans, participant accounts and expenses.
EBP_ACCOUNT_TABLES: frozenset[str] = frozenset(
    {"ebp_participant_loans", "ebp_loan_offsets", "ebp_participant_balances", "ebp_sdba_holdings"}
    | {"ebp_plan_expenses", "ebp_erisa_budget_lines", "ebp_compliance_tests"}
    | {"ebp_qualification_facts"}
)
# A-07-T08 (0668, DEC-2302): letters, report and release; versions and acts insert-only.
A07_LETTER_INSERT_ONLY: frozenset[str] = frozenset(
    {"representation_letter_versions", "representation_letter_approvals"}
    | {"governance_communication_versions", "governance_communication_sends"}
    | {"governance_acknowledgements", "audit_report_versions", "report_releases"}
)
A07_LETTER_TABLES: frozenset[str] = (
    A07_LETTER_INSERT_ONLY
    | {"representation_letters", "governance_communications", "governance_recipients"}
    | {"audit_reports"}
)
# A-07-T09 (0669, DEC-2303): the evidence archive; the children insert-only, and `archives` moves
# by status (its v1 rows and a locked row frozen by trigger).
A07_ARCHIVE_INSERT_ONLY: frozenset[str] = frozenset(
    {"archive_binder_indexes", "archive_lock_decisions", "archive_manifests"}
    | {"archive_additions", "archive_addition_decisions"}
)
TABLES: frozenset[str] = (
    A07_ARCHIVE_INSERT_ONLY
    | {"archives"}
    | A07_LETTER_TABLES
    | EBP_ACCOUNT_TABLES
    | EBP_INVESTMENT_TABLES
    | _HUMAN_RECORDS
    | A07_COMPLETION_TABLES
    | EBP_CONTRIBUTION_TABLES
    | EBP_TABLES
    | PLANNING_TABLES
    | EBP_PARTICIPANT_TABLES
    | COMPLETION_TABLES
    | CONTROL_TABLES
)
INSERT_ONLY: frozenset[str] = (
    _HUMAN_RECORDS
    | {"ebp_provider_checks", "ebp_provision_conflicts"}
    | {"materiality_versions", "fraud_minutes_approvals"}
    | {"ebp_population_queries"}
    | {"ebp_plan_reviews"}
    | {"sum_snapshots"}
    | {"walkthroughs"}  # A-04-T25 (0657)
    | {"ebp_payrolls", "ebp_late_remittance_events"}  # A-05-T26 (0658)
    | {"subsequent_events"}  # A-07-T07 (0664)
    | {"ebp_certification_evaluations", "ebp_schedule_h_mappings"}  # A-05-T35 (0665)
    | A07_LETTER_INSERT_ONLY  # A-07-T08 (0668)
    | A07_ARCHIVE_INSERT_ONLY  # A-07-T09 (0669)
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "eqr_concurrences": frozenset(
        {"tenant_id", "engagement_id", "digest_hash", "not_involved", "concurred_by", "actor_kind"}
        # A-07-T07 (0664): a v2 concurrence's work-item columns (DEC-2261)
        | {"work_item_id", "eqr_review_id", "concurrence_date", "checklist_snapshot_sha256"}
        | {"notes_cleared_count", "mfa_verified_at", "actor_id"}
    ),
    "completion_records": frozenset(
        {"tenant_id", "engagement_id", "kind", "choice", "emphasis", "document_date"}
        | {"evidence_version_id", "report_record_id", "rationale", "recorded_by", "actor_kind"}
    ),
    "releases": frozenset(
        {"tenant_id", "engagement_id", "report_record_id", "report_date", "documentation_due"}
        | {"gates", "released_by", "actor_kind"}
    ),
    "archives": frozenset(
        {"tenant_id", "engagement_id", "seal", "leaf_count", "manifest", "locked_by", "actor_kind"}
        # A-07-T09 (0669): a v2 archive's work-item columns (DEC-2303)
        | {"work_item_id", "release_id", "released_at", "release_date", "retention_policy_id"}
        | {"retention_until", "status", "locked_at", "lock_decision_id", "manifest_id"}
        | {"seal_sha256", "records_object_key", "records_version_id", "gate_snapshot_sha256"}
    ),
    "assurance_phase_events": frozenset(
        {"id", "tenant_id", "engagement_id", "work_item_id", "from_phase", "to_phase", "mode"}
        | {"reason_sealed", "gate_ref", "actor_kind", "actor_user_id", "mfa_at"}
    ),
    "assurance_external_releases": frozenset(
        {"work_item_id", "tenant_id", "engagement_id", "report_released_on", "report_kind"}
        | {"recorded_by", "actor_kind", "mfa_at"}
    ),
    "assurance_external_archives": frozenset(
        {"work_item_id", "tenant_id", "engagement_id", "export_id", "manifest_sha256"}
        | {"firm_tool_ref_sealed", "recorded_by", "actor_kind", "mfa_at"}
    ),
    "ebp_plans": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "plan_entity_id",
            "sponsor_entity_id",
            "plan_year_start",
            "plan_year_end",
            "plan_type",
            "safe_harbor",
            "auto_enrollment",
            "match_formula",
            "qdia",
            "recordkeeper_plan_id",
            "participants_boy_with_balances",
            "participants_eoy",
            "prior_year_filer",
            "form_5558_filed_on",
            "report_target_on",
            "fidelity_bond_amount",
            "plan_document_on",
            "opinion_letter_on",
            "latest_amendment_ref",
            "version",
            "content_hash",
        }
    ),
    "ebp_service_providers": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "org_name",
            "role",
            "contact_id",
            "grant_id",
            "tin_sealed",
            "tin_last4",
            "tin_fingerprint",
            "soc_type",
            "soc_period_start",
            "soc_period_end",
            "soc_evaluation_id",
            "certifies",
            "certification_signed_on",
            "status",
        }
    ),
    "ebp_provider_checks": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "check_kind",
            "provider_id",
            "result",
            "facts",
            "citation_ids",
            "issue_id",
        }
    ),
    "ebp_provisions": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "workpaper_version_id",
            "provision_key",
            "value",
            "reference",
            "citation_id",
            "amendment_effective_on",
            "amendment_citation_id",
            "origin",
            "suggestion_id",
        }
    ),
    "ebp_plan_reviews": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "workpaper_id",
            "review_no",
            "document_version_ids",
            "amendment_in_force",
            "started_by",
        }
    ),
    "ebp_provision_conflicts": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "provision_id",
            "kind",
            "governing_citation_id",
            "conflicting_citation_id",
            "issue_id",
        }
    ),
    "materiality_versions": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "version_no",
            "status",
            "basis",
            "tb_snapshot_id",
            "tb_layer",
            "benchmarks",
            "benchmark_key",
            "rate_pct",
            "overall",
            "pm_pct",
            "pm",
            "ct_pct",
            "ct",
            "specific",
            "qualitative_factors",
            "prior_year_overall",
            "policy_version_id",
            "decision_card_id",
            "decision_id",
            "reassessment",
            "impact",
            "engine_name",
            "engine_version",
            "inputs_hash",
            "computed_at",
            "created_by_kind",
            "created_by_user_id",
            "on_behalf_of_user_id",
        }
    ),
    "risk_register_rows": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "code",
            "level",
            "area_key",
            "area_label",
            "assertions",
            "inherent_risk",
            "control_risk",
            "rmm",
            "rmm_policy_version_id",
            "significance",
            "fraud",
            "presumption_kind",
            "inherent_factors",
            "rationale",
            "status",
            "approved_card_id",
            "content_hash",
            "version_no",
        }
    ),
    "risk_linkages": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "risk_id",
            "target_kind",
            "target_ref",
            "state",
            "suggestion_id",
        }
    ),
    "service_organizations": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "name",
            "services",
            "relevant",
            "evidence_type",
            "status",
            "subservice_orgs",
            "third_party_contact_id",
        }
    ),
    "fraud_brainstorm_sessions": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "held_at",
            "medium",
            "led_by_user_id",
            "attendees",
            "excluded",
            "discussion",
            "presumed_risk_conclusions",
            "minutes_text",
            "minutes_hash",
            "minutes_status",
            "minutes_source",
        }
    ),
    "fraud_minutes_approvals": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "session_id",
            "minutes_hash",
            "approved_by_user_id",
            "actor_kind",
        }
    ),
    "fraud_inquiries": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "respondent_contact_id",
            "governance_body_ref",
            "questionnaire_id",
        }
    ),
    "ebp_source_imports": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "evidence_version_id",
            "kind",
            "column_map",
            "row_count",
            "totals",
            "sha256",
            "status",
            "refusal_code",
            "imported_by",
        }
    ),
    "ebp_participants": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "import_id",
            "participant_key",
            "name",
            "ssn_sealed",
            "ssn_fp",
            "ssn_last4",
            "dob_sealed",
            "dob_fp",
            "hire_on",
            "termination_on",
            "status",
            "compensation",
            "deferral_election_pct",
            "years_of_service",
            "vested_pct",
        }
    ),
    "ebp_population_queries": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "import_id",
            "rule_key",
            "inputs_hash",
            "engine_version",
            "result_keys",
            "count",
        }
    ),
    "audit_findings": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "issue_id",
            "ref",
            "kind",
            "route",
            "compliance_standard",
            "coso_component",
            "title",
            "why_surfaced_sealed",
            "why_surfaced_suggestion_id",
            "created_by_kind",
            "agent_run_id",
            "materiality_version_id",
            "evaluation",
            "consultation_id",
        }
    ),
    "deficiencies": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "finding_id",
            "status",
            "severity_proposed",
            "severity_proposed_by_kind",
            "severity_suggestion_id",
        }
    ),
    "audit_misstatements": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "finding_id",
            "ref",
            "origin_ref",
            "type",
            "nature",
            "status",
            "amount",
            "column_set",
            "fs_effect",
            "carried_from_py",
            "py_ref",
            "projection",
            "materiality_version_id",
            "proposed_entry_id",
        }
    ),
    "sum_snapshots": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "version_no",
            "materiality_version_id",
            "column_set",
            "engine_version",
            "inputs_hash",
            "totals",
            "qualitative_factors",
            "purpose",
            "decision_card_id",
            "created_by",
        }
    ),
    "consultations": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "ref",
            "question_sealed",
            "raised_by",
            "consulted_with_user_id",
            "links",
        }
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "ebp_plans": frozenset(
        {
            "plan_entity_id",
            "sponsor_entity_id",
            "safe_harbor",
            "auto_enrollment",
            "match_formula",
            "qdia",
            "recordkeeper_plan_id",
            "participants_boy_with_balances",
            "participants_eoy",
            "prior_year_filer",
            "form_5558_filed_on",
            "report_target_on",
            "fidelity_bond_amount",
            "plan_document_on",
            "opinion_letter_on",
            "latest_amendment_ref",
            "version",
            "content_hash",
        }
    ),
    "ebp_service_providers": frozenset(
        {
            "org_name",
            "contact_id",
            "grant_id",
            "tin_sealed",
            "tin_last4",
            "tin_fingerprint",
            "soc_type",
            "soc_period_start",
            "soc_period_end",
            "soc_evaluation_id",
            "certifies",
            "certification_signed_on",
            "status",
        }
    ),
    "ebp_provisions": frozenset(
        {
            "value",
            "reference",
            "citation_id",
            "amendment_effective_on",
            "amendment_citation_id",
            "origin",
            "suggestion_id",
        }
    ),
    "risk_register_rows": frozenset(
        {
            "area_label",
            "assertions",
            "inherent_risk",
            "control_risk",
            "rmm",
            "rmm_policy_version_id",
            "significance",
            "fraud",
            "inherent_factors",
            "rationale",
            "status",
            "approved_card_id",
            "content_hash",
            "version_no",
            "updated_at",
        }
    ),
    "risk_linkages": frozenset(
        {
            "state",
            "suggestion_id",
            "removed_at",
        }
    ),
    "service_organizations": frozenset(
        {
            "services",
            "relevant",
            "evidence_type",
            "status",
            "subservice_orgs",
            "third_party_contact_id",
            "soc_report_id",
            "row_version",
            "updated_at",
        }
    ),
    "fraud_brainstorm_sessions": frozenset(
        {
            "held_at",
            "medium",
            "led_by_user_id",
            "attendees",
            "excluded",
            "discussion",
            "presumed_risk_conclusions",
            "minutes_text",
            "minutes_hash",
            "minutes_status",
            "minutes_source",
            "updated_at",
            "row_version",  # A-04-T19 (0651, DEC-2055)
        }
    ),
    "fraud_inquiries": frozenset(
        {
            "answered_at",
        }
    ),
    "audit_findings": frozenset(
        {
            "route",
            "kind",
            "coso_component",
            "title",
            "evaluation",
            "version",
        }
    ),
    "deficiencies": frozenset(
        {
            "status",
            "severity_proposed",
            "severity_proposed_by_kind",
            "severity_suggestion_id",
            "severity_concluded",
            "decision_card_id",
            "decision_id",
            "communicated_ref",
            "communicated_at",
            "version",
        }
    ),
    "audit_misstatements": frozenset(
        {
            "ref",
            "status",
            "amount",
            "fs_effect",
            "projection",
            "proposed_entry_id",
            "passed_by",
            "passed_reason_sealed",
            "version",
        }
    ),
    "consultations": frozenset(
        {
            "status",
            "conclusion_sealed",
            "concluded_at",
        }
    ),
    "ebp_source_imports": frozenset(
        {
            "status",
            "refusal_code",
            "row_count",
            "totals",
        }
    ),
}

# A-04-T25 (0657, DEC-2206): internal control and SOC 1, as the migration grants them.
INSERT_COLUMNS.update(
    {
        "control_activities": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "process_name", "design"}
            | {"implementation", "reliance", "service_organization_id"}
        ),
        "walkthroughs": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "control_activity_id"}
            | {"performed_on", "performed_by_user_id", "evidence_version_ids"}
        ),
        "control_exceptions": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "workpaper_id", "sheet_row"}
            | {"matter", "description", "proposed_severity", "disposition", "coso_component"}
            | {
                "proposed_by_kind",
                "proposed_by_user_id",
            }  # 0657's CHECK: a severity names its proposer
            | {"misstatement_candidate_amount", "suggestion_id", "citation_ids"}
            | {"recorded_by_kind"}
        ),
        "soc_report_evaluations": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "service_organization_id"}
            | {"evidence_version_id", "service_auditor_name", "opinion", "report_type"}
            | {"period_start", "period_end", "report_date", "objectives_total"}
            | {"objectives_relevant"}
        ),
        "soc_exceptions": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "evaluation_id", "co_ref"}
            | {"description", "impact", "impact_rationale"}
        ),
        "cuecs": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "evaluation_id", "n", "text"}
            | {"control_activity_id", "evidence_refs", "status", "page_citation_id"}
        ),
    }
)
UPDATE_COLUMNS.update(
    {
        "control_activities": frozenset(
            {"design", "implementation", "reliance", "service_organization_id"}
            | {"row_version", "updated_at"}
        ),
        "control_exceptions": frozenset(
            {"matter", "description", "proposed_severity", "proposed_by_kind"}
            | {"proposed_by_user_id", "disposition", "coso_component"}
            | {"misstatement_candidate_amount", "routed_kind", "routed_ref", "suggestion_id"}
            | {"citation_ids", "row_version", "updated_at"}
        ),
        "soc_report_evaluations": frozenset(
            {"service_auditor_name", "opinion", "report_type", "period_start", "period_end"}
            | {"report_date", "objectives_total", "objectives_relevant"}
            | {"bridge_letter_request_item_id", "bridge_letter_evidence_version_id"}
            | {"gap_days", "engine_version", "inputs_hash", "reliance_state"}
            | {"reliance_card_id", "row_version", "updated_at"}
        ),
        "soc_exceptions": frozenset({"impact", "impact_rationale", "routed_ref", "updated_at"}),
        "cuecs": frozenset(
            {"control_activity_id", "evidence_refs", "status", "page_citation_id", "updated_at"}
        ),
    }
)

# A-05-T26 (0658, DEC-2207): EBP contributions. Payrolls are as imported and computed; a late
# remittance's correction columns move through its events (a correction is a person's).
INSERT_COLUMNS.update(
    {
        "ebp_payrolls": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "import_id", "pay_date"}
            | {"deferrals_pretax", "deferrals_roth", "match", "deposit_date"}
            | {"business_day_lag", "calendar_lag", "result", "engine_name", "engine_version"}
            | {"inputs_hash", "citation_ids"}
        ),
        "ebp_late_remittances": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "payroll_id", "principal", "due_on"}
            | {"deposited_on", "business_days_late", "interest_days", "rate", "rate_ref"}
            | {"lost_earnings", "excise_exposure", "schedule_h_4a", "engine_name"}
            | {"engine_version", "inputs_hash"}
        ),
        "ebp_late_remittance_events": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "late_remittance_id", "event"}
            | {"payload", "evidence_version_ids", "actor_kind", "actor_user_id"}
        ),
    }
)
UPDATE_COLUMNS["ebp_late_remittances"] = frozenset(
    {"interest_days", "rate", "rate_ref", "lost_earnings", "excise_exposure", "schedule_h_4a"}
    | {"engine_name", "engine_version", "inputs_hash", "finding_id", "correction_status"}
    | {"lost_earnings_deposited_on", "scc_notice_on", "form_5330_status", "version"}
    | {"updated_at"}
)

# A-07-T07 (0664, DEC-2232): EQR and completion. Digest-card content never changes (only the
# reviewed and superseded columns move); subsequent events are insert-only.
INSERT_COLUMNS.update(
    {
        "eqr_reviews": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "eqr_user_id", "assignment_ref"}
            | {"eligibility_snapshot", "status"}
        ),
        "eqr_checklist_items": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "eqr_review_id", "item_key"}
            | {"template_version_id", "position", "status", "sub_line", "updated_by"}
        ),
        "eqr_digest_cards": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "eqr_review_id", "source_kind"}
            | {
                "source_ref",
                "title",
                "snapshot",
                "snapshot_sha256",
                "citation_ids",
                "built_by_run_id",
            }
        ),
        "completion_items": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "item_key", "template_version_id"}
            | {"position", "status", "derived", "evidence_text", "link_target", "gate_tag"}
            | {"depends_on_client", "due_on", "na_basis_sealed", "na_by", "last_event_id"}
        ),
        "subsequent_event_procedures": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "procedure_key", "performed_through"}
            | {"performed_by", "status", "run_id"}
        ),
        "subsequent_events": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "description_sealed", "recognition"}
            | {"fs_effect_sealed", "note_ref", "citation_ids", "recorded_by", "actor_kind"}
            | {"actor_id"}
        ),
        "legal_letters": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "not_applicable", "basis_sealed"}
            | {"request_item_id", "status"}
        ),
        "going_concern_evaluations": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "decision_card_id", "inputs"}
            | {"engine_version", "inputs_hash"}
        ),
        "filings": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "form", "filer_name", "preparer_name"}
            | {
                "channel",
                "due_on",
                "extended_due_on",
                "status",
                "filed_on",
                "ack_evidence_version_id",
            }
        ),
    }
)
UPDATE_COLUMNS.update(
    {
        "eqr_reviews": frozenset({"eligibility_snapshot", "status", "version", "updated_at"}),
        "eqr_checklist_items": frozenset(
            {"status", "sub_line", "updated_by", "version", "updated_at"}
        ),
        "eqr_digest_cards": frozenset(
            {"reviewed_at", "reviewed_by", "reviewed_actor_kind", "superseded_by"}
        ),
        "completion_items": frozenset(
            {"status", "derived", "evidence_text", "link_target", "gate_tag", "depends_on_client"}
            | {"due_on", "na_basis_sealed", "na_by", "last_event_id", "version", "updated_at"}
        ),
        "subsequent_event_procedures": frozenset(
            {"performed_through", "performed_by", "status", "run_id", "version", "updated_at"}
        ),
        "legal_letters": frozenset(
            {"not_applicable", "basis_sealed", "request_item_id", "status", "version"}
            | {"updated_at"}
        ),
        "going_concern_evaluations": frozenset(
            {"decision_card_id", "inputs", "engine_version", "inputs_hash", "version"}
            | {"updated_at"}
        ),
        "filings": frozenset(
            {"due_on", "extended_due_on", "status", "filed_on", "ack_evidence_version_id"}
            | {"version", "updated_at"}
        ),
    }
)

# A-05-T35 (0665, DEC-2234): EBP investments and Form 5500; evaluations and mappings insert-only.
INSERT_COLUMNS.update(
    {
        "ebp_trust_report_lines": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "evidence_version_id", "line_key"}
            | {"fund_name", "boy", "eoy", "fair_value_level", "citation_id", "origin"}
        ),
        "ebp_certification_points": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "evidence_version_id", "point_key"}
            | {"proposed_answer", "citation_id"}
        ),
        "ebp_certification_evaluations": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "point_id", "answer", "note"}
            | {"actor_kind", "actor_id"}
        ),
        "ebp_form5500_drafts": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "evidence_version_id", "received_at"}
            | {"plan_year", "preparer_provider_id", "status"}
        ),
        "ebp_form5500_lines": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "draft_id", "line_code", "caption"}
            | {"fs_amount", "f5500_amount", "difference", "classification", "note_ref"}
            | {
                "f5500_citation_id",
                "fs_ref",
                "classified_by_kind",
                "engine_version",
                "inputs_hash",
            }
        ),
        "ebp_part_iv_answers": frozenset(
            {"tenant_id", "engagement_id", "work_item_id", "draft_id", "question", "draft_answer"}
            | {"amount", "evidence_ref", "result", "issue_id"}
        ),
        "ebp_supplemental_schedules": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "kind",
                "rows",
                "total",
                "generated_document_id",
            }
            | {"engine_version", "inputs_hash"}
        ),
        "ebp_schedule_h_mappings": frozenset(
            {"tenant_id", "version", "fs_caption_key", "schedule_h_line", "effective_plan_year"}
            | {"published_at", "published_by"}
        ),
    }
)
UPDATE_COLUMNS.update(
    {
        "ebp_trust_report_lines": frozenset({"superseded_by", "version", "updated_at"}),
        "ebp_certification_points": frozenset(
            {"proposed_answer", "citation_id", "version", "updated_at"}
        ),
        "ebp_form5500_drafts": frozenset({"status", "version", "updated_at"}),
        "ebp_form5500_lines": frozenset(
            {"fs_amount", "f5500_amount", "difference", "classification", "note_ref"}
            | {"fs_ref", "classified_by_kind", "engine_version", "inputs_hash", "version"}
            | {"updated_at"}
        ),
        "ebp_part_iv_answers": frozenset(
            {"draft_answer", "amount", "evidence_ref", "result", "issue_id", "version"}
            | {"updated_at"}
        ),
        "ebp_supplemental_schedules": frozenset(
            {"rows", "total", "generated_document_id", "engine_version", "inputs_hash"}
            | {"version", "updated_at"}
        ),
    }
)

_EBP_SCOPE: frozenset[str] = frozenset({"tenant_id", "engagement_id", "work_item_id"})
_EBP_EVIDENCE: frozenset[str] = frozenset({"evidence_version_id", "citation_id"})
_EBP_SEALED: frozenset[str] = frozenset({"ssn_sealed", "ssn_fp", "ssn_last4"})
# A-05-T41 (0667, DEC-2301): EBP loans, participant accounts and expenses.
INSERT_COLUMNS.update(
    {
        "ebp_participant_loans": _EBP_SCOPE
        | _EBP_EVIDENCE
        | {"participant_key", "loan_ref", "status", "originated_on", "term_months", "is_residence"}
        | {"vested_balance", "beginning_balance", "new_loans", "repayments", "offsets"}
        | {"ending_balance", "limit_amount", "limit_result", "engine_version", "inputs_hash"},
        "ebp_loan_offsets": _EBP_SCOPE
        | _EBP_EVIDENCE
        | {"loan_id", "offset_on", "amount", "form_1099r_code", "reported_line"},
        "ebp_participant_balances": _EBP_SCOPE
        | _EBP_EVIDENCE
        | _EBP_SEALED
        | {"participant_key", "name", "status", "beginning_balance", "contributions", "earnings"}
        | {"distributions", "fees", "transfers", "ending_balance"},
        "ebp_sdba_holdings": _EBP_SCOPE
        | _EBP_EVIDENCE
        | _EBP_SEALED
        | {"participant_key", "security_type", "description", "market_value"},
        "ebp_plan_expenses": _EBP_SCOPE
        | _EBP_EVIDENCE
        | {"provider_id", "line_key", "description", "disclosure_citation_id", "invoiced"}
        | {"credits", "paid_from_plan", "schedule_h_line", "result", "issue_id"},
        "ebp_erisa_budget_lines": _EBP_SCOPE
        | _EBP_EVIDENCE
        | {"line_key", "kind", "amount", "occurred_on"},
        "ebp_compliance_tests": _EBP_SCOPE
        | {"test_key", "plan_year", "limit_amount", "limit_ref", "result", "proposed_by_kind"}
        | {"accepted_by", "accepted_at", "finding_ref", "engine_version", "inputs_hash"},
        "ebp_qualification_facts": _EBP_SCOPE
        | _EBP_EVIDENCE
        | {"fact_key", "value", "result", "proposed_by_kind", "accepted_by", "accepted_at"},
    }
)
UPDATE_COLUMNS.update(
    {
        "ebp_participant_loans": frozenset(
            {"status", "vested_balance", "beginning_balance", "new_loans", "repayments"}
            | {"offsets", "ending_balance", "limit_amount", "limit_result", "engine_version"}
            | {"inputs_hash", "citation_id", "version", "updated_at"}
        ),
        "ebp_loan_offsets": frozenset({"citation_id", "form_1099r_code", "version", "updated_at"}),
        "ebp_participant_balances": frozenset(
            {"status", "beginning_balance", "contributions", "earnings", "distributions", "fees"}
            | {"transfers", "ending_balance", "citation_id", "version", "updated_at"}
        ),
        "ebp_sdba_holdings": frozenset(
            {"security_type", "market_value", "citation_id", "version", "updated_at"}
        ),
        "ebp_plan_expenses": frozenset(
            {"disclosure_citation_id", "invoiced", "credits", "paid_from_plan", "schedule_h_line"}
            | {"result", "issue_id", "citation_id", "version", "updated_at"}
        ),
        "ebp_erisa_budget_lines": frozenset({"amount", "citation_id", "version", "updated_at"}),
        "ebp_compliance_tests": frozenset(
            {"limit_amount", "limit_ref", "result", "accepted_by", "accepted_at", "finding_ref"}
            | {"engine_version", "inputs_hash", "version", "updated_at"}
        ),
        "ebp_qualification_facts": frozenset(
            {"value", "result", "accepted_by", "accepted_at", "citation_id", "version"}
            | {"updated_at"}
        ),
    }
)

_A07_SCOPE: frozenset[str] = frozenset({"tenant_id", "engagement_id", "work_item_id"})
_A07_ACTOR: frozenset[str] = frozenset({"actor_kind", "actor_id"})
# A-07-T08 (0668, DEC-2302): letters, report and release.
INSERT_COLUMNS.update(
    {
        "representation_letters": _A07_SCOPE
        | {"template_id", "status", "current_version_id", "envelope_id", "dated_as_of"},
        "representation_letter_versions": _A07_SCOPE
        | {"letter_id", "version_no", "template_version_id", "representations"}
        | {"edited_paragraphs_sealed", "sum_snapshot_id", "content_hash", "drafted_by_run_id"}
        | {"created_by", "generated_document_id"},
        "representation_letter_approvals": _A07_SCOPE
        | _A07_ACTOR
        | {"version_id", "approved_by", "seen_hash", "mfa_verified_at"},
        "governance_communications": _A07_SCOPE
        | {"kind", "standard", "combined_with_id", "due_rule", "due_on", "status"}
        | {"current_version_id", "channel", "envelope_id"},
        "governance_communication_versions": _A07_SCOPE
        | {"communication_id", "version_no", "template_version_id", "sections_sealed"}
        | {"section_refs", "content_hash", "drafted_by_run_id", "created_by"}
        | {"generated_document_id"},
        "governance_communication_sends": _A07_SCOPE
        | _A07_ACTOR
        | {"version_id", "sent_by", "governance_body_id", "recipient_contact_ids", "channel"}
        | {"approval_grant_id", "mfa_verified_at"},
        "governance_recipients": _A07_SCOPE | {"governance_body_id", "ack_required"},
        "governance_acknowledgements": _A07_SCOPE
        | {"communication_id", "version_id", "acknowledged_by_contact_id", "acknowledged_at"}
        | {"channel"},
        "audit_reports": _A07_SCOPE
        | {"report_kind", "framework", "standards_set_id", "template_id", "status"}
        | {"current_version_id", "report_date", "city"},
        "audit_report_versions": _A07_SCOPE
        | {"report_id", "version_no", "choices", "paragraphs", "report_date", "city", "dual_date"}
        | {"reissue_of_release_id", "content_hash", "created_by"},
        "report_releases": _A07_SCOPE
        | _A07_ACTOR
        | {"kind", "reissue_of_id", "report_version_id", "report_version_hash", "released_by"}
        | {"released_at", "report_date", "city", "gate_snapshot", "gate_snapshot_sha256"}
        | {"final_document_version_id", "deliverable_ids", "approval_grant_id"}
        | {"idempotency_key"},
    }
)
UPDATE_COLUMNS.update(
    {
        "representation_letters": frozenset(
            {"status", "current_version_id", "envelope_id", "dated_as_of", "signed_on"}
            | {"g7_met_at", "version", "updated_at"}
        ),
        "governance_communications": frozenset(
            {"combined_with_id", "due_rule", "due_on", "status", "current_version_id", "channel"}
            | {"envelope_id", "version", "updated_at"}
        ),
        "governance_recipients": frozenset({"ack_required", "version", "updated_at"}),
        "audit_reports": frozenset(
            {"status", "current_version_id", "report_date", "city", "version", "updated_at"}
        ),
    }
)

# A-07-T09 (0669, DEC-2303): the evidence archive.
INSERT_COLUMNS.update(
    {
        "archive_binder_indexes": _A07_SCOPE
        | {"archive_id", "index_version", "sections", "sha256", "built_by_kind", "run_id"},
        "archive_lock_decisions": _A07_SCOPE
        | _A07_ACTOR
        | {"archive_id", "decided_by", "assembly_complete_attested", "then_roll_forward"}
        | {"checklist_snapshot", "checklist_sha256", "mfa_verified_at", "approval_grant_id"},
        "archive_manifests": _A07_SCOPE
        | {"archive_id", "manifest_version", "canonicalization", "evidence_leaf_count"}
        | {"row_leaf_count", "run_record_count", "audit_checkpoint_seq_to"}
        | {"audit_checkpoint_root", "merkle_root", "manifest_sha256", "records_object_key"}
        | {"records_version_id", "compliance_retain_until"},
        "archive_additions": _A07_SCOPE
        | {"archive_id", "description_sealed", "reason_code", "evidence_version_id"}
        | {"content_sha256", "added_by", "post_issuance_event_id", "addition_manifest_key"},
        "archive_addition_decisions": _A07_SCOPE
        | _A07_ACTOR
        | {"addition_id", "decision", "decided_by", "reason_sealed", "mfa_verified_at"},
    }
)
UPDATE_COLUMNS["archives"] = frozenset(
    {"status", "locked_at", "locked_by", "lock_decision_id", "manifest_id", "seal_sha256"}
    | {"records_object_key", "records_version_id", "gate_snapshot_sha256", "retention_until"}
)
