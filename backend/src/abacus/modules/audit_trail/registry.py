"""The audit_trail module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file. `audit_events`
itself is the unit of work's (kernel.uow); this module owns its read side.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
# G-02-T10 (migration 0192): the label projection and the export jobs.
TABLES: frozenset[str] = frozenset({"audit_event_labels", "audit_exports"})
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset()
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "audit_event_labels": frozenset(
        {"tenant_id", "seq", "effective_at", "actor_label", "target_label", "keywords"}
        | {"client_id", "office_id", "engagement_id"}
    ),
    "audit_exports": frozenset(
        {"id", "tenant_id", "requested_by", "requested_by_kind", "filter", "from_date"}
        | {"to_date", "include_values", "idempotency_key"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # A rebuildable projection: the indexer re-writes a row on replay (idempotent).
    "audit_event_labels": frozenset(
        {"effective_at", "actor_label", "target_label", "keywords", "client_id", "office_id"}
        | {"engagement_id", "indexed_at"}
    ),
    "audit_exports": frozenset(
        {"status", "seq_from", "seq_to", "row_count", "csv_key", "manifest_key"}
        | {"manifest_sha256", "signature_key_ref", "expires_at", "updated_at"}
    ),
}
