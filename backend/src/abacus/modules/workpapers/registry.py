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
    }
)
INSERT_ONLY: frozenset[str] = TABLES - {"tie_out_checks"}
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "workpapers": frozenset(
        {"tenant_id", "engagement_id", "work_item_id", "code", "title", "audit_area"}
        | {"created_by"}
    ),
    "workpaper_sections": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "title", "position"}
    ),
    "workpaper_cells": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "cell_key", "raw", "value_source"}
        | {"tickmarks", "set_by"}
    ),
    "workpaper_cell_citations": frozenset(
        {"tenant_id", "workpaper_id", "sheet_key", "cell_key", "evidence_version_id"}
        | {"locator", "added_by"}
    ),
    "workpaper_versions": frozenset(
        {"tenant_id", "workpaper_id", "version_no", "content_hash", "content", "created_by"}
    ),
    "tie_out_checks": frozenset(
        {"tenant_id", "engagement_id", "target_type", "target_id", "key", "kind", "created_by"}
    ),
    "tie_out_check_versions": frozenset(
        {"tenant_id", "check_id", "version_no", "label", "actual_selector", "expected"}
        | {"citation_ids", "tolerance", "reason", "created_by", "actor_kind"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "tie_out_checks": frozenset({"current_version_no"}),  # SPEC-310: the current definition
}
