"""The reporting module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. P-11-T05 (0430): C11's six
generated-document tables. P-11-T11 (0522): the sealed render snapshot.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "generated_documents",
        "generated_document_versions",
        "generated_document_files",
        "generated_document_fields",
        "generated_document_events",
        "render_jobs",
        "generated_document_snapshots",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004); each also carries a
# `reporting_rows_immutable` trigger (I-IMMUTABLE).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "generated_document_versions",
        "generated_document_files",
        "generated_document_fields",
        "generated_document_events",
        "generated_document_snapshots",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "generated_documents": frozenset(
        {"id", "tenant_id", "kind", "owner_type", "owner_id", "client_id", "engagement_id"}
        | {"work_item_id", "template_id", "created_by_kind"}
    ),
    "generated_document_versions": frozenset(
        {"id", "tenant_id", "generated_document_id", "version_no", "mode"}
        | {"template_version_id", "layout_key", "layout_version", "snapshot_key"}
        | {"snapshot_sha256", "content_hash", "engine_version", "approval_ref"}
        | {"requested_by_kind", "requested_by_user_id", "requested_by_run_id"}
        | {"on_behalf_of_user_id"}
    ),
    "generated_document_files": frozenset(
        {"id", "tenant_id", "version_id", "format", "evidence_version_id", "sample_object_key"}
        | {"render_hash", "page_count", "byte_size"}
    ),
    "generated_document_fields": frozenset(
        {"id", "tenant_id", "version_id", "field_key", "occurrence", "label", "page"}
        | {"rect_pt", "value_text", "match_id"}
    ),
    "generated_document_events": frozenset(
        {"id", "tenant_id", "generated_document_id", "kind", "cause_ref", "changed_keys"}
        | {"actor_kind", "actor_user_id"}
    ),
    "render_jobs": frozenset(
        {"id", "tenant_id", "generated_document_id", "target_version_no", "workflow_id"}
    ),
    "generated_document_snapshots": frozenset(
        {"id", "tenant_id", "version_id", "snapshot", "snapshot_sha256"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "generated_documents": frozenset(),  # identity and scope never move
    "render_jobs": frozenset({"status", "failure_code", "started_at", "finished_at"}),
}
