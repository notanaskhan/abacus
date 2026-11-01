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
    }
)
INSERT_ONLY: frozenset[str] = TABLES - {
    "tie_out_checks", "attention_flags", "program_procedures", "attribute_tests"
}  # fmt: skip
INSERT_COLUMNS: dict[str, frozenset[str]] = {
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
    ),
    "workpaper_cell_citations": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "cell_key", "evidence_version_id"}
        | {"locator", "added_by"}
    ),
    "workpaper_versions": frozenset(
        {"tenant_id", "workpaper_id", "version_no", "content_hash", "content", "created_by"}
        | {"produced_by_kind", "agent_run_id", "on_behalf_of_user_id", "cause"}  # 0581
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
