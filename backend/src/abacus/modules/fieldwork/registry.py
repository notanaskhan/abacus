"""The fieldwork module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "engagement_materiality",  # SPEC-037 (TASK-083)
        "fieldwork_settings",
        "procedures",
        "populations",
        "selections",
        "selected_items",
        "engagement_accounts",  # SPEC-038 (TASK-086)
        "item_results",  # SPEC-037 (TASK-084)
        "selection_approvals",  # SPEC-040 (TASK-100)
        "review_notes",  # SPEC-041 (TASK-103)
        "findings",  # SPEC-043 (TASK-107)
        "procedure_session_events",  # SPEC-044 (TASK-109)
        "misstatements",
        "materiality_decisions",  # SPEC-300 (TASK-301)
        "risks",
        "risk_versions",
        "risk_approvals",
        "finding_severities",  # SPEC-301 (TASK-302)
        "finding_communications",
        "adjustments",
        "adjustment_lines",
        "adjustment_events",
        "representations",
        "representation_removals",
        "review_note_events",
        "item_signoffs",  # SPEC-040 (TASK-100)
        "item_support_requests",
        "procedure_conclusions",
        "workpaper_versions",
        "workpaper_signatures",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "engagement_materiality",  # SPEC-037 (TASK-083): versions
        "fieldwork_settings",  # SPEC-037 (TASK-083): versions
        "populations",  # SPEC-037 (TASK-083): ADR-132
        "selections",  # SPEC-037 (TASK-083): ADR-132
        "selected_items",  # SPEC-037 (TASK-083): ADR-132
        "engagement_accounts",  # SPEC-038 (TASK-086): confirmations, as made
        "item_results",  # TASK-084
        "selection_approvals",  # SPEC-040 (TASK-100): decisions, as made
        "review_notes",  # SPEC-041 (TASK-103): notes, as written
        "findings",  # SPEC-043 (TASK-107): as raised and recorded
        "procedure_session_events",  # SPEC-044 (TASK-109): plan approvals, as given
        "misstatements",  # SPEC-043 (TASK-107): as raised and recorded
        "materiality_decisions",  # SPEC-300 (TASK-301)
        "risks",  # SPEC-300 (TASK-301)
        "risk_versions",  # SPEC-300 (TASK-301)
        "risk_approvals",  # SPEC-300 (TASK-301)
        "finding_severities",
        "finding_communications",
        "adjustments",
        "adjustment_lines",
        "adjustment_events",  # SPEC-301
        "representations",  # SPEC-301
        "representation_removals",  # SPEC-301
        "review_note_events",  # SPEC-041 (TASK-103): notes, as written
        "item_signoffs",  # SPEC-040 (TASK-100): decisions, as made
        "item_support_requests",  # TASK-084
        "procedure_conclusions",  # TASK-084
        "workpaper_versions",  # SPEC-037 (TASK-084): ADR-131
        "workpaper_signatures",  # SPEC-037 (TASK-084): ADR-131
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # Fieldwork (SPEC-037; TASK-083): materiality, firm defaults, procedures and selections.
    "engagement_materiality": frozenset(
        {"tenant_id", "engagement_id", "overall", "performance", "trivial", "benchmark", "set_by"}
        | {"basis_amount", "rate_pct", "performance_pct", "trivial_pct", "rationale"}  # SPEC-300
    ),
    "fieldwork_settings": frozenset({"tenant_id", "settings", "set_by"}),
    "procedures": frozenset(
        {"id", "tenant_id", "engagement_id", "definition", "definition_version", "parameters"}
        | {"started_by"}
    ),
    "populations": frozenset(
        {"id", "tenant_id", "procedure_id", "gl_snapshot_id", "rule_version", "entry_count"}
        | {"line_count", "total_debit", "total_credit", "tied", "failure"}
    ),
    "selections": frozenset(
        {"id", "tenant_id", "procedure_id", "population_id", "parameters", "criteria_version"}
        | {"random_method", "seed", "item_count", "created_by"}
    ),
    "selected_items": frozenset(
        {"tenant_id", "selection_id", "position", "posted_on", "kind", "reference"}
        | {"counterparty", "line_nos", "accounts", "amount", "descriptions", "rules", "reason"}
        | {"band", "recorded_bill_reference", "recorded_bill_date"}  # SPEC-038 (TASK-087)
    ),
    "engagement_accounts": frozenset(  # SPEC-038 (TASK-086)
        {"tenant_id", "engagement_id", "role", "account_codes", "confirmed_by"}
    ),
    "item_results": frozenset(
        {"tenant_id", "selected_item_id", "result", "note", "evidence_version_ids"}
        | {"recorded_by", "relates_to_year"}
        | {"adopted_assessment_id"}  # SPEC-044 (TASK-109)
    ),
    "selection_approvals": frozenset(
        {"tenant_id", "selection_id", "approved_by", "note"}
    ),  # SPEC-040 (TASK-100)
    "review_notes": frozenset(
        {"tenant_id", "engagement_id", "procedure_id", "selected_item_id", "body", "raised_by"}
    ),  # SPEC-041 (TASK-103)
    "findings": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "procedure_id",
            "selected_item_id",
            "title",
            "description",
            "raised_by",
        }
    ),  # SPEC-043 (TASK-107)
    # Fieldwork results and workpapers (SPEC-037; TASK-084; ADR-131).
    "procedure_session_events": frozenset(
        {"tenant_id", "procedure_id", "kind", "by_user"}
    ),  # SPEC-044 (TASK-109)
    "misstatements": frozenset(
        {"tenant_id", "finding_id", "kind", "amount", "account_code", "corrected", "recorded_by"}
    ),  # SPEC-043
    # Planning (SPEC-300; TASK-301): the partner's materiality decision and the risk register.
    "materiality_decisions": frozenset({"tenant_id", "materiality_id", "rationale", "decided_by"}),
    "risks": frozenset({"tenant_id", "engagement_id", "number", "raised_by"}),
    "risk_versions": frozenset(
        {"tenant_id", "risk_id", "title", "area", "level", "assertions", "inherent", "control"}
        | {"significant", "fraud", "rationale", "recorded_by"}
    ),
    "risk_approvals": frozenset({"tenant_id", "risk_version_id", "rationale", "approved_by"}),
    # Completion (SPEC-301; TASK-302): severity, proposed entries and representations.
    "finding_severities": frozenset(
        {"tenant_id", "finding_id", "stage", "severity", "rationale", "set_by"}
    ),
    "finding_communications": frozenset(
        {"tenant_id", "finding_id", "communicated_on", "recipients", "recorded_by"}
    ),
    "adjustments": frozenset(
        {"tenant_id", "engagement_id", "kind", "number", "finding_id", "description", "raised_by"}
    ),
    "adjustment_lines": frozenset(
        {"tenant_id", "adjustment_id", "position", "account_code", "debit", "credit"}
    ),
    "adjustment_events": frozenset({"tenant_id", "adjustment_id", "kind", "note", "by_user"}),
    "representations": frozenset(
        {"tenant_id", "engagement_id", "body", "finding_id", "adjustment_id", "raised_by"}
    ),
    "representation_removals": frozenset({"tenant_id", "representation_id", "removed_by"}),
    "review_note_events": frozenset(
        {"tenant_id", "review_note_id", "kind", "body", "by_user"}
    ),  # SPEC-041 (TASK-103)
    "item_signoffs": frozenset(
        {"tenant_id", "selected_item_id", "item_result_id", "level", "signed_by"}
    ),  # SPEC-040 (TASK-100)
    "item_support_requests": frozenset(
        {"tenant_id", "selected_item_id", "request_item_id", "requested_by"}
    ),
    "procedure_conclusions": frozenset({"tenant_id", "procedure_id", "text", "written_by"}),
    "workpaper_versions": frozenset(
        {"id", "tenant_id", "procedure_id", "version", "selection_id", "result_ids"}
        | {"conclusion_id", "materiality_id", "sha256"}
    ),
    "workpaper_signatures": frozenset(
        {"tenant_id", "workpaper_version_id", "kind", "signed_by", "role"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "procedures": frozenset({"parameters", "status", "failure_code"}),  # SPEC-037 (TASK-083)
}
