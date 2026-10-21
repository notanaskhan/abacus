"""The ledger module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "gl_snapshots",  # SPEC-034 (TASK-069)
        "gl_account_balances",
        "gl_entries",
        "ledger_snapshots",
        "trial_balance_lines",
        "trial_balances",  # SPEC-309 (TASK-320): the trial balance of record
        "trial_balance_versions",
        "trial_balance_annotations",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "gl_snapshots",  # SPEC-034 (TASK-069): ADR-004
        "gl_account_balances",  # SPEC-034 (TASK-069): ADR-004
        "gl_entries",  # SPEC-034 (TASK-069): ADR-004
        "ledger_snapshots",
        "trial_balance_lines",
        "trial_balance_versions",  # SPEC-309 (TASK-320)
        "trial_balance_annotations",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # General ledger detail (SPEC-034; TASK-069): snapshots, balances, entries; imports.
    "gl_snapshots": frozenset(
        {"id", "tenant_id", "client_entity_id", "period_start", "period_end", "source"}
        | {"raw_fingerprint", "tb_snapshot_id", "line_count", "total_debit", "total_credit"}
        | {"kind"}  # SPEC-038 (TASK-086)
    ),
    "gl_account_balances": frozenset(
        {"tenant_id", "snapshot_id", "account_code", "account_name", "opening", "debit"}
        | {"credit", "closing", "tb_closing", "opening_derived"}
    ),
    "gl_entries": frozenset(
        {"tenant_id", "snapshot_id", "line_no", "account_code", "posted_on", "reference"}
        | {"kind", "counterparty", "description", "debit", "credit", "source_ref"}
    ),
    "ledger_snapshots": frozenset(
        {"id", "tenant_id", "client_entity_id", "period_start", "period_end", "pulled_at"}
        | {"source", "raw_fingerprint", "line_count", "total_debit", "total_credit"}
    ),
    "trial_balance_lines": frozenset(
        {"id", "tenant_id", "snapshot_id", "account_code", "account_name", "debit"}
        | {"credit", "source_ref"}
    ),
    # SPEC-309 (TASK-320): the trial balance of record, its versions and annotations.
    "trial_balances": frozenset(
        {"tenant_id", "engagement_id", "work_item_id", "client_entity_id", "label"}
        | {"period_start", "period_end", "display_unit", "created_by"}
    ),
    "trial_balance_versions": frozenset(
        {"tenant_id", "trial_balance_id", "client_entity_id", "version_no", "snapshot_id"}
        | {"prior_snapshot_id", "adopted_by", "actor_kind", "reason", "content_fingerprint"}
    ),
    "trial_balance_annotations": frozenset(
        {"tenant_id", "trial_balance_id", "account_code", "area", "wp_ref", "reason", "set_by"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "trial_balances": frozenset({"current_version_no"}),  # SPEC-309: the current version
}
