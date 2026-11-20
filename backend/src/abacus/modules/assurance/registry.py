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
# A-05-T48 (0685): AUD-27's estimates, related parties and parties in interest; search runs
# insert-only.
EBP_ESTIMATES_RP_TABLES: frozenset[str] = frozenset(
    {"accounting_estimates", "estimate_components", "related_parties"}
    | {"related_party_search_runs", "parties_in_interest"}
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
# R-02-T05 (0710; R-02 §4.2): governance bodies (DEC-93) and the client's acknowledgement of
# uncorrected misstatements, insert-only and human-only.
R02_GOVERNANCE_TABLES: frozenset[str] = frozenset(
    {"governance_bodies", "governance_body_members", "uncorrected_misstatement_acknowledgements"}
)
_TABLES: frozenset[str] = (
    A07_ARCHIVE_INSERT_ONLY
    | R02_GOVERNANCE_TABLES
    | {  # A-05-T48
        "accounting_estimates",
        "estimate_components",
        "parties_in_interest",
        "related_parties",
        "related_party_search_runs",
    }
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
_INSERT_ONLY: frozenset[str] = (
    _HUMAN_RECORDS
    | {"ebp_provider_checks", "ebp_provision_conflicts"}
    | {"materiality_versions", "fraud_minutes_approvals"}
    | {"ebp_population_queries"}
    | {"ebp_plan_reviews"}
    | {"sum_snapshots"}
    | {"walkthroughs"}  # A-04-T25 (0657)
    | {"ebp_payrolls", "ebp_late_remittance_events"}  # A-05-T26 (0658)
    | {"related_party_search_runs"}  # A-05-T48 (0685)
    | {"subsequent_events"}  # A-07-T07 (0664)
    | {"ebp_certification_evaluations", "ebp_schedule_h_mappings"}  # A-05-T35 (0665)
    | A07_LETTER_INSERT_ONLY  # A-07-T08 (0668)
    | A07_ARCHIVE_INSERT_ONLY  # A-07-T09 (0669)
    | {"uncorrected_misstatement_acknowledgements"}  # R-02-T05 (0710)
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
            "match_ytd",  # 0673 (A-05-T32, DEC-2361)
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
            | {"description"}  # A-05-T58 remainder (0744)
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
            | {"keyed_by", "keyed_note_sealed"}  # A-05-T58 close (0742)
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
        | {"ending_balance", "limit_amount", "limit_result", "engine_version", "inputs_hash"}
        | {"interest_rate"},  # A-05-T58 remainder (0744)
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
            | {"template_id"}  # 0802 (TASK-6740): a choice follows the newest published template
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
        # `id`: the addition manifest names the addition before its row exists (0814, S35
        # follow-up: the insert was refused without it).
        "archive_additions": _A07_SCOPE
        | {"id", "archive_id", "description_sealed", "reason_code", "evidence_version_id"}
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

# A-05-T48 (0685): AUD-27. A screen-out and a conclusion are a person's (the services, A-05 §4.3).
_AUD27_SCOPE = frozenset({"tenant_id", "engagement_id", "work_item_id", "id"})
INSERT_COLUMNS.update(
    {
        "accounting_estimates": _AUD27_SCOPE
        | {"account_ref", "name", "balance", "significant_risk", "method", "rollforward"}
        | {"retrospective", "range_low", "range_high", "bias", "disclosure_ref", "je_ref"}
        | {"created_by_kind"},
        "estimate_components": _AUD27_SCOPE | {"estimate_id", "label", "amount", "position"},
        "related_parties": _AUD27_SCOPE
        | {"name_sealed", "display_ref", "source", "relationship", "inquiry_ref"}
        | {"created_by_kind"}
        | {"transactions", "disclosure", "disclosure_note"},  # A-05-T57 close (0743)
        "related_party_search_runs": _AUD27_SCOPE
        | {"run_id", "inputs", "candidates", "vendors_searched", "customers_searched"},
        "parties_in_interest": _AUD27_SCOPE
        | {"name", "erisa_relationship", "transactions", "exemption", "reporting"}
        | {"created_by_kind"},
    }
)
UPDATE_COLUMNS.update(
    {
        "accounting_estimates": frozenset(
            {"account_ref", "balance", "significant_risk", "method", "rollforward"}
            | {"retrospective", "range_low", "range_high", "bias", "disclosure_ref", "je_ref"}
            | {"status", "decision_card_id", "finding_id", "version", "updated_at"}
        ),
        "estimate_components": frozenset({"label", "amount", "position"}),
        "related_parties": frozenset(
            {"status", "screened_out_reason", "screened_out_by", "screened_out_at", "finding_id"}
            | {"inquiry_ref", "version", "updated_at"}
            | {"transactions", "disclosure", "disclosure_note"}  # A-05-T57 close (0743)
        ),
        "parties_in_interest": frozenset(
            {"erisa_relationship", "transactions", "exemption", "reporting", "version"}
            | {"updated_at"}
        ),
    }
)

# R-02-T05 (0710): a body's members change by ending a row and adding one; an acknowledgement is
# the client's own act (its actor is the session's, I-AGENT-NEVER).
INSERT_COLUMNS.update(
    {
        "governance_bodies": frozenset(
            {"id", "tenant_id", "client_id", "client_entity_id", "name", "kind"}
        ),
        "governance_body_members": frozenset(
            {"id", "tenant_id", "body_id", "contact_id", "member_role", "started_on"}
        ),
        "uncorrected_misstatement_acknowledgements": frozenset(
            {"id", "tenant_id", "engagement_id", "work_item_id", "sum_snapshot_id"}
            | {"approval_item_id", "net_effect", "engine_version", "inputs_hash", "entry_ids"}
            | {"contact_id", "actor_user_id", "actor_kind", "actor_id", "principal_kind"}
            | {"grant_id", "mfa_verified_at", "seen_hash"}
        ),
    }
)
UPDATE_COLUMNS.update(
    {
        "governance_bodies": frozenset({"name", "kind", "status", "version", "updated_at"}),
        "governance_body_members": frozenset({"member_role", "ended_on"}),
    }
)

# S46: A-08-T16 (0894) confirmations and A-09-T12 (0898) the group audit's records;
# 0898 adds materiality_versions scope and consolidation_id.
_S46_TABLES: frozenset[str] = _TABLES | frozenset(
    {
        "address_verifications",
        "alternative_procedures",
        "component_auditors",
        "component_deliverables",
        "component_instruction_versions",
        "component_instructions",
        "component_milestones",
        "components",
        "confirmation_attachments",
        "confirmation_authorization_items",
        "confirmation_authorizations",
        "confirmation_decisions",
        "confirmation_events",
        "confirmation_lines",
        "confirmation_links",
        "confirmation_responses",
        "confirmations",
        "reconciliation_items",
    }
)
_S46_INSERT_ONLY: frozenset[str] = _INSERT_ONLY | frozenset(
    {
        "address_verifications",
        "alternative_procedures",
        "component_instruction_versions",
        "confirmation_attachments",
        "confirmation_authorization_items",
        "confirmation_decisions",
        "confirmation_events",
        "confirmation_lines",
        "confirmation_links",
        "confirmation_responses",
        "reconciliation_items",
    }
)
INSERT_COLUMNS["address_verifications"] = frozenset(
    {
        "actor_kind",
        "address_sha256",
        "citation_ids",
        "confirmation_id",
        "independent",
        "method",
        "sources",
        "tenant_id",
        "verified_by",
    }
)
INSERT_COLUMNS["alternative_procedures"] = frozenset(
    {"citation_ids", "confirmation_id", "performed_by", "procedure_sealed", "tenant_id"}
)
INSERT_COLUMNS["component_auditors"] = frozenset(
    {
        "city",
        "component_id",
        "created_by",
        "engagement_id",
        "ep_contact_id",
        "organisation_name",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["component_auditors"] = frozenset(
    {
        "city",
        "competence_evaluated_at",
        "competence_evaluated_by",
        "component_id",
        "ep_contact_id",
        "independence_confirmed_at",
        "make_reference",
        "organisation_name",
        "peer_review_obtained_on",
        "questionnaire_received_on",
        "row_version",
    }
)
INSERT_COLUMNS["component_deliverables"] = frozenset(
    {"component_auditor_id", "due_on", "engagement_id", "tenant_id", "title", "work_item_id"}
)
UPDATE_COLUMNS["component_deliverables"] = frozenset(
    {
        "evidence_item_id",
        "received_at",
        "return_reason",
        "returned_at",
        "reviewed_actor_kind",
        "reviewed_at",
        "reviewed_by",
        "row_version",
        "status",
        "went_late_at",  # 0945 (A-09-T27): stamped once by the late sweep
    }
)
INSERT_COLUMNS["component_instruction_versions"] = frozenset(
    {
        "content_hash",
        "created_by",
        "drafted_by_run_id",
        "engagement_id",
        "generated_document_id",
        "instructions_id",
        "sections",
        "tenant_id",
        "version_no",
        "work_item_id",
    }
)
INSERT_COLUMNS["component_instructions"] = frozenset(
    {"component_auditor_id", "engagement_id", "tenant_id", "work_item_id"}
)
UPDATE_COLUMNS["component_instructions"] = frozenset(
    {
        "acknowledged_at",
        "acknowledged_contact_id",
        "current_version_id",
        "row_version",
        "sent_actor_kind",
        "sent_at",
        "sent_by",
        "status",
    }
)
INSERT_COLUMNS["component_milestones"] = frozenset(
    {
        "component_auditor_id",
        "deliverable_id",
        "due_on",
        "engagement_id",
        "kind",
        "label",
        "position",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["component_milestones"] = frozenset({"deliverable_id", "due_on", "position"})
INSERT_COLUMNS["components"] = frozenset(
    {
        "component_auditor_id",
        "component_pm",
        "consolidation_entity_id",
        "created_by",
        "engagement_id",
        "performed_by",
        "planned_work",
        "scope_areas",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["components"] = frozenset(
    {
        "component_auditor_id",
        "component_pm",
        "performed_by",
        "planned_work",
        "row_version",
        "scope_areas",
    }
)
INSERT_COLUMNS["confirmation_decisions"] = frozenset(
    {"actor_kind", "confirmation_id", "content_hash", "decided_by", "decision", "tenant_id"}
)
INSERT_COLUMNS["confirmation_events"] = frozenset(
    {"actor_id", "actor_kind", "confirmation_id", "kind", "tenant_id"}
)
INSERT_COLUMNS["confirmation_lines"] = frozenset(
    {"account_last4", "book_amount", "confirmation_id", "description", "position", "tenant_id"}
)
INSERT_COLUMNS["confirmation_links"] = frozenset({"confirmation_id", "principal_id", "tenant_id"})
# A-08-T18 (0932, DEC-5324): one C7 authorization per request and the confirmations it covers.
INSERT_COLUMNS["confirmation_authorizations"] = frozenset(
    {
        "engagement_id",
        "letter_evidence_version_id",
        "requested_by",
        "signer_contact_id",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["confirmation_authorization_items"] = frozenset(
    {"authorization_id", "confirmation_id", "tenant_id"}
)
UPDATE_COLUMNS["confirmation_authorizations"] = frozenset({"completed_at", "envelope_id"})
# A-08-T19 (0932, DEC-5325): the files a respondent's link uploaded for its confirmation.
INSERT_COLUMNS["confirmation_attachments"] = frozenset(
    {"confirmation_id", "evidence_version_id", "principal_id", "tenant_id"}
)
INSERT_COLUMNS["confirmation_responses"] = frozenset(
    {
        "accounts",  # A-08-T19 (0932): the respondent's own account list (bank)
        "agrees",
        "attachment_version_ids",
        "attested",
        "confirmation_id",
        "confirmed_total",
        "explanation_sealed",
        "ip_sealed",  # A-08-T19 (0932): the P-14 access record, sealed
        "respondent_name_sealed",
        "tenant_id",
        "user_agent",
        "via",
    }
)
INSERT_COLUMNS["confirmations"] = frozenset(
    {
        "address_sealed",
        "address_sha256",
        "channel",
        "created_by",
        "engagement_id",
        "number",
        "respondent_name_sealed",
        "respondent_org",
        "sample_item_ref",
        "tb_account_refs",
        "tenant_id",
        "type",
        "work_item_id",
    }
)
UPDATE_COLUMNS["confirmations"] = frozenset({"row_version", "status"})
INSERT_COLUMNS["reconciliation_items"] = frozenset(
    {"amount", "citation_ids", "confirmation_id", "created_by", "kind", "tenant_id"}
)
INSERT_COLUMNS["materiality_versions"] = INSERT_COLUMNS.get(
    "materiality_versions", frozenset()
) | frozenset(
    {
        "basis",
        "benchmark_key",
        "benchmarks",
        "computed_at",
        "consolidation_id",
        "created_by_kind",
        "created_by_user_id",
        "ct",
        "ct_pct",
        "decision_card_id",
        "decision_id",
        "engagement_id",
        "engine_name",
        "engine_version",
        "impact",
        "inputs_hash",
        "on_behalf_of_user_id",
        "overall",
        "pm",
        "pm_pct",
        "policy_version_id",
        "prior_year_overall",
        "qualitative_factors",
        "rate_pct",
        "reassessment",
        "scope",
        "specific",
        "status",
        "tb_layer",
        "tb_snapshot_id",
        "tenant_id",
        "version_no",
        "work_item_id",
    }
)

# A-08-T21 (0940, DEC-5400): audit analytics. Sets are recomputed as new versions (their status
# and stamp move); lines, expectations, prior-year imports and sent questions are insert-only;
# an explanation is insert-only but for its one acceptance stamp.
A08T21_TABLES: frozenset[str] = frozenset(
    {
        "analytics_explanations",
        "analytics_expectations",
        "analytics_lines",
        "analytics_questions",
        "analytics_sets",
        "prior_year_figures",
    }
)
A08T21_INSERT_ONLY: frozenset[str] = frozenset(
    {"analytics_expectations", "analytics_lines", "analytics_questions", "prior_year_figures"}
)
INSERT_COLUMNS["analytics_sets"] = frozenset(
    {
        "basis_label",
        "created_by",
        "cy_layer",
        "cy_trial_balance_id",
        "engagement_id",
        "engine_version",
        "kind",
        "materiality_version_id",
        "provisional",
        "py_source",
        "run_parameters",
        "stage",
        "tenant_id",
        "threshold_amount",
        "threshold_pct",
        "threshold_policy_version_id",
        "version_no",
        "work_item_id",
    }
)
UPDATE_COLUMNS["analytics_sets"] = frozenset(
    {
        "computed_at",
        "content_hash",
        "failure_code",
        "inputs_hash",
        "status",
        "superseded_by",
        "tb_balanced",
    }
)
INSERT_COLUMNS["analytics_lines"] = frozenset(
    {
        "caption",
        "cell",
        "change",
        "change_pct",
        "cy",
        "derived",
        "evaluated",
        "fs_line_key",
        "group_key",
        "over",
        "position",
        "py",
        "set_id",
        "sources",
        "status",
        "tenant_id",
    }
)
INSERT_COLUMNS["analytics_explanations"] = frozenset(
    {
        "accepted_at",
        "accepted_by",
        "answered_by_contact_id",
        "authored_by",
        "carried_from_id",
        "citation_ids",
        "line_position",
        "question_id",
        "set_id",
        "source",
        "suggestion_id",
        "tenant_id",
        "text",
    }
)
UPDATE_COLUMNS["analytics_explanations"] = frozenset({"accepted_at", "accepted_by"})
INSERT_COLUMNS["analytics_expectations"] = frozenset(
    {
        "basis",
        "citation_ids",
        "high",
        "line_position",
        "low",
        "pct_high",
        "pct_low",
        "set_by",
        "set_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["prior_year_figures"] = frozenset(
    {
        "amount",
        "citation_id",
        "engagement_id",
        "fs_line_key",
        "import_no",
        "imported_by",
        "source",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["analytics_questions"] = frozenset(
    {
        "line_position",
        "question_id",
        "questionnaire_id",
        "sent_by",
        "set_id",
        "template_key",
        "tenant_id",
    }
)

# A-08-T22 (0941, DEC-5401): an SSARS inquiry program, published once by a person.
A08T22_TABLES: frozenset[str] = frozenset({"ssars_inquiry_programs"})
INSERT_COLUMNS["ssars_inquiry_programs"] = frozenset(
    {
        "created_by",
        "engagement_id",
        "methodology_program_id",
        "questionnaire_ids",
        "questions",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["ssars_inquiry_programs"] = frozenset({"published_at", "published_by"})

# A-08-T24 (0943, DEC-5403): the run rows a person started on AUD-12, AUD-13, AUD-26, AUD-14.
A08T24_TABLES: frozenset[str] = frozenset({"fieldwork_run_rows"})
INSERT_COLUMNS["fieldwork_run_rows"] = frozenset(
    {
        "code_result",
        "engagement_id",
        "idempotency_key",
        "initiator_user_id",
        "items",
        "kind",
        "run_ids",
        "target_id",
        "target_kind",
        "tenant_id",
        "work_item_id",
    }
)

# A-09-T27 (0944, DEC-5405): a person's instructions send, completed or undone once.
A09T27_TABLES: frozenset[str] = frozenset({"component_instruction_sends"})
INSERT_COLUMNS["component_instruction_sends"] = frozenset(
    {
        "content_hash",
        "engagement_id",
        "generated_document_id",
        "instructions_id",
        "recipient_contact_id",
        "sent_by",
        "tenant_id",
        "version_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["component_instruction_sends"] = frozenset(
    {"completed_at", "grant_id", "undone_at"}
)

# Q-05-T09 (0983, DEC-5712): the consultations log v2 beside A-06's record; all insert-only.
Q05T09_TABLES: frozenset[str] = frozenset(
    {"consultation_links", "consultation_positions", "consultation_resolutions"}
)
INSERT_COLUMNS["consultation_links"] = frozenset(
    {"tenant_id", "consultation_id", "target_kind", "target_id", "linked_by"}
)
INSERT_COLUMNS["consultation_positions"] = frozenset(
    {"tenant_id", "consultation_id", "role", "agrees", "position_sealed", "recorded_by"}
)
INSERT_COLUMNS["consultation_resolutions"] = frozenset(
    {"tenant_id", "consultation_id", "resolution_sealed", "resolved_by"}
)
UPDATE_COLUMNS["consultations"] = UPDATE_COLUMNS["consultations"] | frozenset(
    {"implemented", "implemented_reference", "reopened_at"}
)
# S51 partials (0985, DEC-5723): a new consultation's facts and consulted role.
INSERT_COLUMNS["consultations"] = INSERT_COLUMNS["consultations"] | frozenset(
    {"facts_sealed", "consulted_role"}
)

# Q-05-T12 (0984, DEC-5714): post-issuance cases; comparisons and evaluations insert-only.
Q05T12_TABLES: frozenset[str] = frozenset(
    {"post_issuance_events", "post_issuance_comparisons", "post_issuance_evaluations"}
    | {"post_issuance_sources"}  # Q-05-T17 (0997)
)
Q05T12_INSERT_ONLY: frozenset[str] = frozenset(
    {"post_issuance_comparisons", "post_issuance_evaluations"}
)
INSERT_COLUMNS["post_issuance_events"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "ref", "type", "standard", "source_kind",
     "received_at", "description_sealed", "created_by"}
)  # fmt: skip
UPDATE_COLUMNS["post_issuance_events"] = frozenset({"status"})
INSERT_COLUMNS["post_issuance_sources"] = frozenset(
    {"tenant_id", "case_id", "evidence_version_id", "filed_from", "created_by"}
)
# S51 partials (0986, DEC-5724): the source evidence and the EP's decision on the case row.
INSERT_COLUMNS["post_issuance_events"] = INSERT_COLUMNS["post_issuance_events"] | frozenset(
    {"source_evidence_version_id"}
)
UPDATE_COLUMNS["post_issuance_events"] = UPDATE_COLUMNS["post_issuance_events"] | frozenset(
    {"decision", "decided_by", "decided_at", "rationale_sealed", "decided_actor_kind"}
)
INSERT_COLUMNS["post_issuance_comparisons"] = frozenset(
    {"tenant_id", "event_id", "line_key", "as_certified", "as_corrected", "difference"}
)
INSERT_COLUMNS["post_issuance_evaluations"] = frozenset(
    {"tenant_id", "event_id", "total_difference", "clearly_trivial", "overall_materiality",
     "share_pct", "below_clearly_trivial", "disclosure_affected", "materiality_version_id"}
)  # fmt: skip

# Every table and insert-only table above, combined once.
TABLES: frozenset[str] = (
    _S46_TABLES
    | A08T21_TABLES
    | A08T22_TABLES
    | A08T24_TABLES
    | A09T27_TABLES
    | Q05T09_TABLES
    | Q05T12_TABLES
)
INSERT_ONLY: frozenset[str] = (
    _S46_INSERT_ONLY | A08T21_INSERT_ONLY | A08T24_TABLES | Q05T09_TABLES | Q05T12_INSERT_ONLY
)
