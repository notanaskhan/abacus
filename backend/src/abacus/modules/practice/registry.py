"""The practice module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# I-01-T12 (migration 0320): HOME-01's client activity projection. Inserted once per event and
# pruned after 90 days (the app role may delete), never updated.
TABLES: frozenset[str] = frozenset({"home_activity_items"})
INSERT_ONLY: frozenset[str] = frozenset()
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "home_activity_items": frozenset(
        {"tenant_id", "source_event_id", "event_type", "occurred_at", "client_id"}
        | {"engagement_id", "work_item_id", "office_id", "actor_kind", "actor_ref"}
        | {"subject_ref", "facts"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}

# T-08-T07 (0962, DEC-5606).
T08T07_TABLES: frozenset[str] = frozenset(
    {
        "filing_deadline_alerts",
        "filing_deadlines",
    }
)
TABLES = TABLES | T08T07_TABLES
INSERT_ONLY = INSERT_ONLY | frozenset(
    {
        "filing_deadline_alerts",
    }
)
INSERT_COLUMNS["filing_deadlines"] = frozenset(
    {
        "client_id",
        "done_at",
        "due_on",
        "extended_due_on",
        "extension_filed_on",
        "extension_form",
        "filing_label",
        "inputs_hash",
        "internal_target_on",
        "office_id",
        "original_due_on",
        "owner_user_ids",
        "postponed_from",
        "postponement_notice_id",
        "reference_set_version_ids",
        "rule_key",
        "service_line",
        "signer_user_id",
        "source_kind",
        "source_ref",
        "stage_code",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["filing_deadlines"] = frozenset(
    {
        "client_id",
        "computed_at",
        "done_at",
        "due_on",
        "extended_due_on",
        "extension_filed_on",
        "extension_form",
        "inputs_hash",
        "internal_target_on",
        "office_id",
        "original_due_on",
        "owner_user_ids",
        "postponed_from",
        "postponement_notice_id",
        "reference_set_version_ids",
        "rule_key",
        "service_line",
        "signer_user_id",
        "stage_code",
        "work_item_id",
    }
)
INSERT_COLUMNS["filing_deadline_alerts"] = frozenset(
    {
        "due_on",
        "filing_deadline_id",
        "tenant_id",
        "threshold",
    }
)

# Q-05-T05 (0963, DEC-5611).
Q05T05_TABLES: frozenset[str] = frozenset(
    {
        "agent_output_outcomes",
        "annual_evaluations",
        "draft_final_field_facts",
        "inspection_selection_rules",
        "inspections",
        "qm_cycles",
        "qm_finding_evaluations",
        "qm_finding_links",
        "qm_findings",
        "qm_objectives",
        "qm_register_imports",
        "qm_response_risks",
        "qm_responses",
        "qm_risk_assessment_reviews",
        "qm_risks",
        "qm_settings",
    }
)
TABLES = TABLES | Q05T05_TABLES
INSERT_ONLY = INSERT_ONLY | frozenset(
    {
        "inspection_selection_rules",
        "qm_finding_evaluations",
        "qm_finding_links",
        "qm_register_imports",
        "qm_risk_assessment_reviews",
    }
)
INSERT_COLUMNS["qm_settings"] = frozenset(
    {
        "evaluation_as_of_month_day",
        "operational_owner_user_id",
        "tenant_id",
        "ultimate_responsible_user_id",
    }
)
UPDATE_COLUMNS["qm_settings"] = frozenset(
    {
        "evaluation_as_of_month_day",
        "operational_owner_user_id",
        "ultimate_responsible_user_id",
        "updated_at",
    }
)
INSERT_COLUMNS["qm_cycles"] = frozenset(
    {
        "as_of",
        "starts_on",
        "tenant_id",
        "year",
    }
)
INSERT_COLUMNS["qm_objectives"] = frozenset(
    {
        "component",
        "owner_user_id",
        "ref",
        "tenant_id",
        "title",
    }
)
UPDATE_COLUMNS["qm_objectives"] = frozenset(
    {
        "active",
        "health_flag",
        "note_sealed",
        "owner_user_id",
        "version",
    }
)
INSERT_COLUMNS["qm_risks"] = frozenset(
    {
        "objective_id",
        "ref",
        "tenant_id",
        "title",
    }
)
UPDATE_COLUMNS["qm_risks"] = frozenset(
    {
        "title",
    }
)
INSERT_COLUMNS["qm_responses"] = frozenset(
    {
        "frequency",
        "objective_id",
        "owner_user_id",
        "ref",
        "tenant_id",
        "title",
    }
)
UPDATE_COLUMNS["qm_responses"] = frozenset(
    {
        "frequency",
        "owner_user_id",
        "title",
    }
)
INSERT_COLUMNS["qm_response_risks"] = frozenset(
    {
        "response_id",
        "risk_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["qm_register_imports"] = frozenset(
    {
        "counts",
        "kind",
        "published_by",
        "source_evidence_version_id",
        "status",
        "tenant_id",
    }
)
INSERT_COLUMNS["qm_risk_assessment_reviews"] = frozenset(
    {
        "note_sealed",
        "reviewed_by",
        "reviewed_on",
        "tenant_id",
    }
)
INSERT_COLUMNS["inspection_selection_rules"] = frozenset(
    {
        "created_by",
        "seed",
        "tenant_id",
        "version",
        "weights",
    }
)
INSERT_COLUMNS["inspections"] = frozenset(
    {
        "basis",
        "cycle_id",
        "due_on",
        "ep_signer_user_id",
        "inspected_engagement_id",
        "inspector_user_id",
        "kind",
        "ref",
        "risk_score",
        "rule_version",
        "selected_because",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["inspections"] = frozenset(
    {
        "concluded_on",
        "due_on",
        "inspector_user_id",
        "status",
        "version",
    }
)
INSERT_COLUMNS["qm_findings"] = frozenset(
    {
        "agent_key",
        "cycle_id",
        "due_on",
        "inspection_id",
        "owner_user_id",
        "raised_by_kind",
        "ref",
        "source",
        "tenant_id",
        "title_sealed",
    }
)
UPDATE_COLUMNS["qm_findings"] = frozenset(
    {
        "due_on",
        "owner_user_id",
        "remediated_at",
        "remediation_note_sealed",
        "remediation_sealed",
        "root_cause_category",
        "root_cause_sealed",
        "status",
        "version",
    }
)
INSERT_COLUMNS["qm_finding_evaluations"] = frozenset(
    {
        "evaluated_by",
        "evaluation",
        "finding_id",
        "rationale_sealed",
        "tenant_id",
    }
)
INSERT_COLUMNS["qm_finding_links"] = frozenset(
    {
        "created_by",
        "finding_id",
        "link_kind",
        "ref",
        "tenant_id",
    }
)
INSERT_COLUMNS["annual_evaluations"] = frozenset(
    {
        "cycle_id",
        "responsible_user_id",
        "tenant_id",
    }
)
UPDATE_COLUMNS["annual_evaluations"] = frozenset(
    {
        "checklist",
        "decision_card_id",
        "memo_evidence_version_id",
        "root_cause_reviewed_at",
        "root_cause_reviewed_by",
    }
)
INSERT_COLUMNS["agent_output_outcomes"] = frozenset(
    {
        "agent_key",
        "decided_at",
        "decided_by",
        "engagement_id",
        "office_id",
        "outcome",
        "reason_code",
        "service_line",
        "source_event_id",
        "source_id",
        "source_kind",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["agent_output_outcomes"] = frozenset(
    {
        "decided_at",
        "decided_by",
        "outcome",
        "reason_code",
    }
)
INSERT_COLUMNS["draft_final_field_facts"] = frozenset(
    {
        "agent_drafted",
        "changed_before_filing",
        "field_class",
        "filed_at",
        "office_id",
        "return_id",
        "tenant_id",
    }
)
UPDATE_COLUMNS["draft_final_field_facts"] = frozenset(
    {
        "agent_drafted",
        "changed_before_filing",
        "filed_at",
    }
)
