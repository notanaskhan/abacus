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
    }
)
INSERT_ONLY: frozenset[str] = TABLES
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
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
