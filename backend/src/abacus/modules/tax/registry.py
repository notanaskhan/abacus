"""The tax module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. Empty until its first table.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {"tax_returns"}  # F-03-T22 (0089)
    | {"tax_return_status_events", "return_engine_summaries"}  # T-02-T07 (0403)
    | {"engine_return_links", "engine_sync_events"}  # T-01-T19 (0465)
    | {"engine_import_diffs", "engine_diagnostics"}  # T-01-T19 (0465)
)
# T-02-T07 (0403): `tax_returns` takes updates of its v1 columns now, so it is no longer
# insert-only; its events and engine summaries are.
INSERT_ONLY: frozenset[str] = frozenset(
    {"tax_return_status_events", "return_engine_summaries", "engine_sync_events"}
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "tax_returns": frozenset(
        {"tenant_id", "work_item_id", "engagement_id", "client_entity_id", "form", "tax_year"}
    ),
}
INSERT_COLUMNS["tax_return_status_events"] = frozenset(
    {"tenant_id", "work_item_id", "from_status", "to_status", "event", "actor_kind", "actor_id"}
    | {"on_behalf_of", "reason"}
)
INSERT_COLUMNS["return_engine_summaries"] = frozenset(
    {"id", "tenant_id", "work_item_id", "import_id", "engine_version", "kind", "lines"}
    | {"plan_items", "carryforwards", "prior_year", "approved_at"}
)
# T-01-T19 (0465): the engine bridge.
INSERT_COLUMNS["engine_return_links"] = frozenset(
    {"tenant_id", "return_id", "engine", "engine_return_id"}
)
INSERT_COLUMNS["engine_sync_events"] = frozenset(
    {"tenant_id", "return_id", "kind", "engine_return_id", "version", "file_name", "file_key"}
    | {"file_version", "file_size", "payload_sha256", "actor_user_id", "summary"}
    | {"write_operation_id"}
)
INSERT_COLUMNS["engine_import_diffs"] = frozenset(
    {"tenant_id", "return_id", "sync_event_id", "checkpoint_id", "engine_return_id", "version"}
    | {"rows"}
)
INSERT_COLUMNS["engine_diagnostics"] = frozenset(
    {"tenant_id", "return_id", "sync_event_id", "code", "severity", "field_key", "message_text"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "engine_return_links": frozenset({"version"}),
    "engine_import_diffs": frozenset(
        {"status", "approved_checkpoint_id", "decided_by", "decided_at", "row_version"}
    ),
    "engine_diagnostics": frozenset({"issue_id"}),
    # T-02-T07 (0403): the v1 columns; `sync_status` and `last_synced_at` only through
    # `tax.api.record_sync_state` (T-01).
    "tax_returns": frozenset(
        {"fiscal_year_end", "jurisdictions", "filing_status", "engine", "engine_return_id"}
        | {"status", "review_level", "sync_status", "last_synced_at", "extended", "on_hold"}
        | {"approval_policy_version_id", "review_levels_version_id", "original_due_on"}
        | {"extended_due_on", "due_rule_version_ids", "prior_year_return_id", "row_version"}
    ),
}
