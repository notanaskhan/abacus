"""The workpapers module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-308 (TASK-319): working papers, all insert-only. `workpaper_sections` arrives with
# multi-sheet papers; the table exists so the version content can name sheets.
TABLES: frozenset[str] = frozenset(
    {
        "workpapers",
        "workpaper_sections",
        "workpaper_cells",
        "workpaper_cell_citations",
        "workpaper_versions",
        "tie_out_checks",  # SPEC-310 (TASK-321)
        "tie_out_check_versions",
        # 0581 (A-04-T03, DEC-1761): attention flags with their insert-only events, and the
        # engagement's audit procedures (fieldwork's SPEC-300 `procedures` keeps that name).
        "attention_flags",
        "attention_flag_events",
        "program_procedures",
        # 0642 (A-05-T15, DEC-1959): the shared attribute grid and its insert-only results.
        "attribute_tests",
        "test_attribute_results",
        # 0930 (A-08-T14, DEC-5306): the AUD-12 deviation log, insert-only.
        "control_deviations",
    }
)
INSERT_ONLY: frozenset[str] = TABLES - {
    "tie_out_checks", "attention_flags", "program_procedures", "attribute_tests"
}  # fmt: skip
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "control_deviations": frozenset(
        {"tenant_id", "engagement_id", "work_item_id", "test_id", "sample_item_id"}
        | {"attribute_key", "kind", "description", "difference", "below_ct", "finding_id"}
        | {"recorded_by", "actor_kind"}
    ),
    "workpapers": frozenset(
        {"tenant_id", "engagement_id", "work_item_id", "code", "title", "audit_area"}
        | {"created_by"}
        | {"kind", "program_step_keys"}  # 0581 (A-04-T03)
    ),
    "workpaper_sections": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "title", "position"} | {"band_kind"}
    ),
    "workpaper_cells": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "cell_key", "raw", "value_source"}
        | {"tickmarks", "set_by"}
        # 0581 (A-04-T03): the structured address, the typed value and its state.
        | {"section_key", "row_key", "col_key", "value", "value_state", "suggestion_id"}
        | {"classification", "updated_version_no"}
        # 0830 (T-05-T20): a formula cell's source and inputs, and the engine that set it.
        | {"formula", "formula_inputs", "engine_name", "engine_version"}
    ),
    "workpaper_cell_citations": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "cell_key", "evidence_version_id"}
        | {"locator", "added_by"}
    ),
    "workpaper_versions": frozenset(
        {"tenant_id", "workpaper_id", "version_no", "content_hash", "content", "created_by"}
        | {"produced_by_kind", "agent_run_id", "on_behalf_of_user_id", "cause"}  # 0581
        | {"engine_manifest", "inputs_hash"}  # 0830 (T-05-T20): "Version 2 · Run 2"
    ),
    # 0581 (A-04-T03): the scope columns are set by `workpaper_child_scope()` from the workpaper,
    # and the actor kind from the session, never by the caller.
    "attention_flags": frozenset(
        {"tenant_id", "workpaper_id", "section_key", "row_key", "kind", "text", "created_by"}
        | {"agent_run_id"}
    ),
    "attention_flag_events": frozenset(
        {"tenant_id", "workpaper_id", "flag_id", "event", "actor_user_id", "agent_run_id", "ref"}
    ),
    "program_procedures": frozenset(
        {"tenant_id", "engagement_id", "work_item_id", "methodology_version_id"}
        | {"program_step_key", "level", "mandatory", "created_by"}
        | {"linked_work"}  # 0614 (A-04-T07)
    ),
    "tie_out_checks": frozenset(
        {"tenant_id", "engagement_id", "target_type", "target_id", "key", "kind", "created_by"}
    ),
    "tie_out_check_versions": frozenset(
        {"tenant_id", "check_id", "version_no", "label", "actual_selector", "expected"}
        | {"citation_ids", "tolerance", "reason", "created_by", "actor_kind"}
    ),
    "attribute_tests": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "workpaper_id",
            "variant",
            "sample_set_id",
            "sample_set_version",
            "attributes",
            "version_no",
            "content_hash",
        }
    ),
    "test_attribute_results": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "test_id",
            "sample_item_id",
            "attribute_key",
            "seq",
            "value",
            "citation_ids",
            "result",
            "note_sealed",
            "trace",
            "suggestion_id",
        }
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "tie_out_checks": frozenset(
        {"current_version_no"}  # SPEC-310: the current definition
        | {"issue_id", "issue_linked_by", "issue_linked_at"}  # 0193 (A-02-T11): the issue link
    ),
    # 0581 (A-04-T03): a flag converts or resolves; a procedure is tailored or moves on.
    "attention_flags": frozenset({"state", "converted_to_kind", "converted_to_id"}),
    "program_procedures": frozenset(
        {"tailored", "tailored_rationale", "status", "linked_work"}
        | {"row_version"}  # 0614 (A-04-T07): a tailoring names the version it saw
    ),
    "attribute_tests": frozenset(
        {
            "attributes",
            "version_no",
            "content_hash",
        }
    ),
}

# K-03-T13 (1012, TASK-8903): the Sheets engine core
TABLES = TABLES | frozenset(
    {
        "agent_column_previews",
        "agent_column_run_rows",
        "agent_column_runs",
        "agent_columns",
        "sheet_cells",
        "sheet_columns",
        "sheet_row_links",
        "sheet_rows",
        "sheet_sections",
        "sheet_views",
        "sheets",
    }
)
INSERT_COLUMNS["agent_column_previews"] = frozenset(
    {
        "agent_column_id",
        "created_by",
        "engagement_id",
        "id",
        "instruction_hash",
        "row_ids",
        "sheet_id",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["agent_column_previews"] = frozenset({"agent_run_id", "results", "status"})
INSERT_COLUMNS["agent_column_run_rows"] = frozenset(
    {"engagement_id", "row_id", "run_id", "sheet_id", "state", "tenant_id", "work_item_id"}
)
UPDATE_COLUMNS["agent_column_run_rows"] = frozenset(
    {"child_run_id", "evidence_version_id", "failure_code", "state", "suggestion_id", "updated_at"}
)
INSERT_COLUMNS["agent_column_runs"] = frozenset(
    {
        "agent_column_id",
        "budget_override_by",
        "engagement_id",
        "estimate_minutes",
        "id",
        "initiator_kind",
        "rows_now",
        "rows_on_arrival",
        "rows_targeted",
        "run_number",
        "scope",
        "sheet_id",
        "started_by",
        "tenant_id",
        "trigger_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["agent_column_runs"] = frozenset(
    {
        "agent_run_id",
        "finished_at",
        "rows_now",
        "rows_on_arrival",
        "status",
        "stopped_at",
        "stopped_by",
    }
)
INSERT_COLUMNS["agent_columns"] = frozenset(
    {
        "default_scope",
        "engagement_id",
        "instruction_doc",
        "instruction_hash",
        "mention_refs",
        "options",
        "output_type",
        "runs_as_capability",
        "sheet_column_id",
        "sheet_id",
        "skill_key",
        "skill_version_id",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["agent_columns"] = frozenset(
    {
        "default_scope",
        "instruction_doc",
        "instruction_hash",
        "mention_refs",
        "options",
        "output_type",
        "saved_at",
        "saved_by",
        "saved_preview_id",
        "skill_key",
        "skill_version_id",
        "status",
        "version",
    }
)
INSERT_COLUMNS["sheet_cells"] = frozenset(
    {
        "column_id",
        "engagement_id",
        "last_edited_at",
        "last_edited_by",
        "previous_value",
        "row_id",
        "sheet_id",
        "suggestion_id",
        "tenant_id",
        "value",
        "value_state",
        "work_item_id",
    }
)
UPDATE_COLUMNS["sheet_cells"] = frozenset(
    {"last_edited_at", "last_edited_by", "previous_value", "suggestion_id", "value", "value_state"}
)
INSERT_COLUMNS["sheet_columns"] = frozenset(
    {
        "classification",
        "classification_reason",
        "client_visible",
        "column_key",
        "config",
        "default_value",
        "description",
        "engagement_id",
        "frozen",
        "id",
        "name",
        "origin",
        "position",
        "required",
        "sheet_id",
        "template_column_ref",
        "tenant_id",
        "type",
        "validation",
        "width",
        "work_item_id",
    }
)
UPDATE_COLUMNS["sheet_columns"] = frozenset(
    {
        "classification",
        "classification_reason",
        "client_visible",
        "config",
        "default_value",
        "deleted_at",
        "deleted_by",
        "description",
        "frozen",
        "name",
        "position",
        "required",
        "validation",
        "version",
        "width",
    }
)
INSERT_COLUMNS["sheet_row_links"] = frozenset(
    {
        "engagement_id",
        "kind",
        "linked_by",
        "row_id",
        "sheet_id",
        "target_id",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["sheet_rows"] = frozenset(
    {
        "created_by",
        "engagement_id",
        "id",
        "position",
        "row_key",
        "scoped_out_by_rule",
        "section_key",
        "sheet_id",
        "source_ref",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["sheet_rows"] = frozenset(
    {"position", "row_version", "scoped_out_by_rule", "section_key"}
)
INSERT_COLUMNS["sheet_sections"] = frozenset(
    {
        "engagement_id",
        "parent_section_key",
        "position",
        "section_key",
        "sheet_id",
        "tenant_id",
        "title",
        "totals_spec",
        "work_item_id",
    }
)
UPDATE_COLUMNS["sheet_sections"] = frozenset({"position", "title", "totals_spec"})
INSERT_COLUMNS["sheet_views"] = frozenset(
    {
        "created_by",
        "engagement_id",
        "filters",
        "group_by",
        "id",
        "name",
        "shared",
        "sheet_id",
        "sort",
        "tenant_id",
        "view_key",
        "visible_columns",
        "work_item_id",
    }
)
UPDATE_COLUMNS["sheet_views"] = frozenset(
    {"filters", "group_by", "name", "shared", "sort", "version", "visible_columns"}
)
INSERT_COLUMNS["sheets"] = frozenset(
    {
        "created_by",
        "engagement_id",
        "id",
        "kind",
        "procedure_id",
        "sample_set_id",
        "sample_version",
        "sheet_definition_id",
        "sheet_key",
        "template_version_id",
        "tenant_id",
        "title",
        "work_item_id",
    }
)
UPDATE_COLUMNS["sheets"] = frozenset({"sample_set_id", "sample_version", "title", "version"})
UPDATE_COLUMNS["program_procedures"] = UPDATE_COLUMNS["program_procedures"] | frozenset(
    {"scoped_out_by_rule"}
)  # K-03-T13 (1012, TASK-8903): the Sheets engine core
