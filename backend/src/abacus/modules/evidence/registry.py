"""The evidence module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "evidence_items",
        "evidence_versions",
        "inbox_files",
        "upload_extractions",  # SPEC-029 (TASK-054)
        "upload_checks",  # SPEC-029 (TASK-055)
        "upload_previews",  # SPEC-029 (TASK-056)
        "upload_preview_pages",
        "review_decisions",
        "review_assignments",
        "review_reason_codes",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "evidence_versions",
        "upload_extractions",  # SPEC-029 (TASK-054): a derived record, rebuilt, never edited
        "upload_checks",  # SPEC-029 (TASK-055): what code found, as found
        "upload_previews",  # SPEC-029 (TASK-056): server-made, kept
        "upload_preview_pages",  # SPEC-029 (TASK-056): server-made, kept
        "review_decisions",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "evidence_items": frozenset(
        {"id", "tenant_id", "engagement_id", "title", "created_by_kind", "created_by_id"}
    ),
    "evidence_versions": frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_item_id", "version_no", "fingerprint"}
        | {"storage_key", "storage_version_id", "size_bytes", "media_type", "source", "method"}
        | {"pulled_at", "period_start", "period_end", "client_entity_id", "snapshot_id"}
        | {"idempotency_key"}
        | {"upload_note"}  # SPEC-023: written once, at insert
    ),
    # SPEC-023 (TASK-039): files dropped at the engagement level, waiting to be matched.
    "inbox_files": frozenset(
        {"tenant_id", "engagement_id", "file_name", "media_type", "size_bytes", "fingerprint"}
        | {"storage_key", "storage_version_id", "uploaded_by", "uploaded_by_staff", "note"}
    ),
    "review_decisions": frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_version_id", "request_item_id"}
        | {"decision", "reason_code", "note", "screening_result_id", "corrects_proposal"}
        | {"actor_kind", "actor_id"}
    ),
    "review_assignments": frozenset(
        {"tenant_id", "evidence_version_id", "engagement_id", "assignee_user_id"} | {"assigned_by"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "inbox_files": frozenset(  # SPEC-023: assigned or discarded, once
        {"status", "assigned_item_id", "assigned_version_id", "decided_by", "decided_at"}
    ),
    "review_assignments": frozenset({"assignee_user_id", "assigned_by", "assigned_at"}),
}
