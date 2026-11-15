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
        "ledger_accounts",  # C-01-T10 (0882): the chart of accounts per snapshot
        "trial_balance_lines",
        "trial_balances",  # SPEC-309 (TASK-320): the trial balance of record
        "trial_balance_versions",
        "trial_balance_annotations",
        # SPEC-316 (TASK-345): grouping sets (firm content) and account mapping.
        "grouping_sets",
        "grouping_set_versions",
        "groupings",
        "fs_lines",
        "fs_line_range_rules",
        "mapping_sets",
        "mapping_set_edits",
        # A-09-T05 (0889): group consolidation (P-63, ADR-341; DEC-66).
        "consolidations",
        "consolidation_entities",
        "consolidation_trial_balances",
        "consolidation_events",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "gl_snapshots",  # SPEC-034 (TASK-069): ADR-004
        "gl_account_balances",  # SPEC-034 (TASK-069): ADR-004
        "gl_entries",  # SPEC-034 (TASK-069): ADR-004
        "ledger_snapshots",
        "ledger_accounts",  # C-01-T10 (0882)
        "trial_balance_lines",
        "trial_balance_versions",  # SPEC-309 (TASK-320)
        "trial_balance_annotations",
        "grouping_sets",  # SPEC-316
        "groupings",
        "fs_lines",
        "fs_line_range_rules",
        "mapping_sets",
        "mapping_set_edits",
        "consolidation_events",  # A-09-T05 (0889): finalized, locked, reopened by a person
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # A-09-T05 (0889): group consolidation.
    "consolidations": frozenset(
        {"id", "tenant_id", "engagement_id", "work_item_id", "name", "year_end"}
        | {"reporting_currency", "interim_period_end", "prior_period_end"}
        | {"source_connection_id", "created_by"}
    ),
    "consolidation_entities": frozenset(
        {"id", "tenant_id", "consolidation_id", "client_entity_id", "parent_id", "level"}
        | {"ownership_pct", "city", "component_auditor_id", "position"}
    ),
    "consolidation_trial_balances": frozenset(
        {"id", "tenant_id", "consolidation_entity_id", "label", "period_kind"}
        | {"period_start", "period_end", "ledger_snapshot_id", "state", "source"}
        | {"evidence_version_id", "not_needed_reason", "attached_by"}
    ),
    "consolidation_events": frozenset(
        {"tenant_id", "consolidation_id", "kind", "reason", "actor_kind", "actor_id"}
    ),
    # General ledger detail (SPEC-034; TASK-069): snapshots, balances, entries; imports.
    "gl_snapshots": frozenset(
        {"id", "tenant_id", "client_entity_id", "period_start", "period_end", "source"}
        | {"raw_fingerprint", "tb_snapshot_id", "line_count", "total_debit", "total_credit"}
        | {"kind"}  # SPEC-038 (TASK-086)
        | {"je_fields_available"}  # A-08-T09 (0888)
    ),
    "gl_account_balances": frozenset(
        {"tenant_id", "snapshot_id", "account_code", "account_name", "opening", "debit"}
        | {"credit", "closing", "tb_closing", "opening_derived"}
    ),
    "gl_entries": frozenset(
        {"tenant_id", "snapshot_id", "line_no", "account_code", "posted_on", "reference"}
        | {"kind", "counterparty", "description", "debit", "credit", "source_ref"}
        | {"offset_account_ref", "payee", "txn_type", "external_txn_id"}  # C-01-T10 (0882)
        | {"posted_by", "entered_at", "source", "approver"}  # A-08-T09 (0888)
    ),
    "ledger_snapshots": frozenset(
        {"id", "tenant_id", "client_entity_id", "period_start", "period_end", "pulled_at"}
        | {"source", "raw_fingerprint", "line_count", "total_debit", "total_credit"}
        | {"label"}  # A-02-T04 (0149); `source_kind` is generated
        | {"source_evidence_version_id", "extraction_run_id"}  # A-05-T28 (0659)
        | {"period_kind", "period"}  # C-01-T10 (0882): monthly CAS snapshots
    ),
    "ledger_accounts": frozenset(
        {"tenant_id", "client_entity_id", "snapshot_id", "external_id", "number", "name"}
        | {"classification", "account_type", "account_subtype", "parent_external_id", "mask"}
        | {"is_contra", "active"}
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
INSERT_COLUMNS.update(
    {
        "grouping_sets": frozenset({"tenant_id", "key", "name", "created_by"}),
        "grouping_set_versions": frozenset(
            {"tenant_id", "grouping_set_id", "version", "payload_hash", "problems", "created_by"}
        ),
        "groupings": frozenset({"tenant_id", "version_id", "key", "label", "class", "position"}),
        "fs_lines": frozenset(
            {"tenant_id", "version_id", "grouping_id", "key", "label", "normal_balance"}
            | {"position"}
        ),
        "fs_line_range_rules": frozenset(
            {"tenant_id", "version_id", "position", "account_from", "account_to", "fs_line_id"}
        ),
        "mapping_sets": frozenset(
            {"tenant_id", "engagement_id", "trial_balance_id", "grouping_set_version_id"}
            | {"created_by"}
            # 0582 (DEC-1769): the prior-year source, fixed at insert
            | {"prior_source", "predecessor_evidence_version_id", "predecessor_keys"}
            | {"taxonomy_kind", "reference_set_version_id"}  # T-05-T26 (0842)
        ),
        "mapping_set_edits": frozenset(
            {"tenant_id", "mapping_set_id", "account_code", "fs_line_id", "edited_by"}
            | {"actor_kind"}
            | {"form_line_key"}  # T-05-T26 (0842)
        ),
    }
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # A-09-T05 (0889): a draft's details and structure; finalize and lock (triggers keep them
    # forward-only); a replaced TB slot points at its successor.
    "consolidations": frozenset(
        {"name", "year_end", "interim_period_end", "prior_period_end", "source_connection_id"}
        | {"status", "lock_state", "finalized_by", "finalized_at", "finalized_actor_kind"}
        | {"locked_by", "locked_at", "locked_actor_kind", "row_version"}
    ),
    "consolidation_entities": frozenset(
        {"parent_id", "level", "city", "component_auditor_id", "position"}
    ),
    "consolidation_trial_balances": frozenset({"superseded_by"}),
    "trial_balances": frozenset({"current_version_no"}),  # SPEC-309: the current version
    # SPEC-316: a draft version is published once (a trigger freezes it afterwards).
    "grouping_set_versions": frozenset(
        {"status", "published_by", "published_at", "published_actor_kind"}
        | {"effective_from"}  # A-03-T06 (0521): the effective date a person publishes with
    ),
}
