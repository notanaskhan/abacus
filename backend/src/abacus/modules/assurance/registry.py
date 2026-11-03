"""The assurance module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-314 (TASK-332): completion, release and archive, all insert-only and human-only.
# A-01-T05 (0134): the record-mode phase events, insert-only and human-only when recorded.
# A-01-T23 (0226): the external release and archive records, insert-only and human-only.
_HUMAN_RECORDS: frozenset[str] = frozenset(
    {"eqr_concurrences", "completion_records", "releases", "archives", "assurance_phase_events"}
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
TABLES: frozenset[str] = (
    _HUMAN_RECORDS
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
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "eqr_concurrences": frozenset(
        {"tenant_id", "engagement_id", "digest_hash", "not_involved", "concurred_by", "actor_kind"}
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
