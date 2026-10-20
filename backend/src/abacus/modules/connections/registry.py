"""The connections module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "ledger_imports",  # SPEC-028 (TASK-052)
        "gl_imports",
        "connections",
        "sync_runs",
        "connection_states",
        "connection_secrets",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "ledger_imports",  # SPEC-028 (TASK-052): an upload and its check are facts
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "gl_imports": frozenset(
        {"id", "tenant_id", "engagement_id", "client_entity_id", "format", "period_start"}
        | {"period_end", "storage_key", "storage_version_id", "fingerprint", "size_bytes"}
        | {"uploaded_by", "on_behalf"}
        | {"kind"}  # SPEC-038 (TASK-086)
    ),
    # SPEC-020 (TASK-036): a client admin connects; states and sealed secrets are the flow's.
    "connections": frozenset(
        {"id", "tenant_id", "client_entity_id", "provider", "scopes", "created_by"}
    ),
    "sync_runs": frozenset(
        {"id", "tenant_id", "connection_id", "engagement_id", "request_item_id", "dataset"}
        | {"period_start", "period_end", "started_by", "client_entity_id"}
    ),
    "connection_states": frozenset(
        {"tenant_id", "engagement_id", "client_entity_id", "user_id", "provider"}
        | {"state_hash", "expires_at"}
    ),
    "connection_secrets": frozenset({"connection_id", "tenant_id", "sealed"}),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "gl_imports": frozenset(  # SPEC-034 (TASK-069): where an upload stands
        {"status", "failure_code", "failure_details", "gl_snapshot_id", "line_count"}
        | {"updated_at"}
    ),
    "connections": frozenset(
        {"status", "last_checked_at", "last_check_ok", "revoked_at", "revoked_by"}
    ),
    "sync_runs": frozenset(
        {"status", "raw_storage_key", "raw_version_id", "raw_fingerprint", "snapshot_id"}
        | {"raw_size_bytes", "raw_pulled_at", "failure_code", "finished_at", "source"}
        | {"evidence_version_id", "queued_reason", "estimated_start_at"}
    ),
    "connection_states": frozenset({"used_at"}),  # SPEC-020: spent once
}
