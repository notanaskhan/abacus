"""The closes module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

_TABLES_PRE_S50: frozenset[str] = frozenset(
    {
        "closes",  # F-03-T22 (0089); lifecycle columns C-01-T09 (0881)
        # C-01-T09 (0881): plans, versions, rows, request templates, templates, procedures.
        "close_plans",
        "close_plan_versions",
        "close_plan_rows",
        "close_request_templates",
        "close_templates",
        "close_procedures",
        # C-01-T11 (0885): reconciliations, schedules, flux and recordings.
        "reconciliations",
        "reconciling_items",
        "reconciling_item_resolutions",
        "statement_lines",
        "reconciliation_matches",
        "arrangements",
        "arrangement_versions",
        "close_schedule_results",
        "analytic_sets",
        "analytic_lines",
        "analytic_explanations",
        "close_entry_recordings",
    }
)
# Insert-only (ADR-004): a recompute or an edit is a new row or version, never an update.
_INSERT_ONLY_PRE_S50: frozenset[str] = frozenset(
    {"close_templates", "reconciliations", "reconciling_item_resolutions", "statement_lines"}
    | {"reconciliation_matches", "arrangements", "arrangement_versions"}
    | {"close_schedule_results", "analytic_sets"}
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "closes": frozenset(
        {"tenant_id", "work_item_id", "engagement_id", "period"}
        | {"client_entity_id", "requests_publish_on", "due_on"}
    ),
    "close_plans": frozenset(
        {"tenant_id", "client_entity_id", "template_key", "close_due_business_day", "created_by"}
    ),
    "close_plan_versions": frozenset(
        {"tenant_id", "plan_id", "version", "effective_from", "change_note", "drafted_by"}
        | {"drafted_by_run_id"}
    ),
    "close_plan_rows": frozenset(
        {"tenant_id", "version_id", "position", "account_external_id", "account_name"}
        | {"account_class", "procedure", "method", "evidence_required", "source"}
        | {"review_level", "frequency", "threshold_ref", "drafted_suggestion_id"}
    ),
    "close_request_templates": frozenset(
        {"tenant_id", "version_id", "title", "category_path", "due_business_day"}
        | {"client_visible", "source_row_ids"}
    ),
    "close_templates": frozenset(
        {"tenant_id", "key", "name", "version", "rows", "request_templates", "imported_by"}
    ),
    "close_procedures": frozenset(
        {"tenant_id", "close_id", "run_id", "run_step_id", "plan_row_id", "group_key"}
        | {"account_external_id", "status", "meta", "open_count", "started_at"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "closes": frozenset(
        {"client_entity_id", "status", "on_hold", "on_hold_reason", "close_plan_version_id"}
        | {"plan_pinned_at", "requests_publish_on", "due_on", "run_no", "locked_at"}
        | {"row_version"}
    ),
    "close_plans": frozenset({"template_key", "close_due_business_day"}),
    "close_plan_versions": frozenset(
        {"status", "effective_from", "change_note", "publish_requested_by"}
        | {"publish_requested_at", "published_by", "published_actor_kind", "published_at"}
        | {"row_version"}
    ),
    "close_plan_rows": frozenset(
        {"position", "account_external_id", "account_name", "account_class", "procedure"}
        | {"method", "evidence_required", "source", "review_level", "frequency"}
        | {"threshold_ref", "adopted_by", "adopted_at"}
    ),
    "close_request_templates": frozenset(
        {"title", "category_path", "due_business_day", "client_visible", "source_row_ids"}
    ),
    "close_procedures": frozenset(
        {"status", "meta", "open_count", "failure_code", "started_at", "finished_at"}
    ),
}

# C-01-T11 (0885).
INSERT_COLUMNS.update(
    {
        "reconciliations": frozenset(
            {"tenant_id", "close_id", "account_external_id", "period", "version"}
            | {
                "statement_evidence_version_id",
                "balance_per_bank",
                "adjusted_bank",
                "book_balance",
            }
            | {"adjusted_book", "difference", "tally", "engine_version", "inputs_hash"}
            | {"content_hash"}
        ),
        "statement_lines": frozenset(
            {"tenant_id", "evidence_version_id", "page_no", "bbox", "txn_date", "description"}
            | {"withdrawal", "deposit", "running_balance", "source_table_id", "confidence"}
        ),
        "reconciling_items": frozenset(
            {"tenant_id", "reconciliation_id", "side", "kind", "ref", "txn_date"}
            | {"days_at_period_end", "amount", "stale", "statement_line_id", "register_line_ref"}
            | {"issue_id", "proposed_entry_id", "carried_from_item_id"}
        ),
        "reconciling_item_resolutions": frozenset(
            {"tenant_id", "item_id", "resolution", "note", "actor_id", "actor_kind"}
        ),
        "reconciliation_matches": frozenset(
            {"tenant_id", "reconciliation_id", "statement_line_id", "register_line_ref"}
            | {"match_rule"}
        ),
        "arrangements": frozenset(
            {"tenant_id", "client_entity_id", "account_external_id", "kind", "created_by"}
        ),
        "arrangement_versions": frozenset(
            {"tenant_id", "arrangement_id", "version", "description", "expense_account_ref"}
            | {"scheduled_total", "starting_balance", "starting_on", "frequency", "start_on"}
            | {"finish_on", "source_citation_id", "actor_id"}
        ),
        "close_schedule_results": frozenset(
            {"tenant_id", "close_id", "arrangement_id", "period", "inflows", "aje"}
            | {"ending_balance", "gl_balance", "tie", "engine_version", "inputs_hash"}
        ),
        "analytic_sets": frozenset(
            {"tenant_id", "close_id", "basis", "threshold_policy_version_id", "version"}
            | {"engine_version", "inputs_hash"}
        ),
        "analytic_lines": frozenset(
            {"tenant_id", "set_id", "position", "line_key", "caption", "prior", "current"}
            | {"change", "change_pct", "test", "status"}
        ),
        "analytic_explanations": frozenset(
            {"tenant_id", "close_id", "line_key", "version", "text_sealed", "drivers"}
            | {"citation_ids", "author_kind", "suggestion_id"}
        ),
        "close_entry_recordings": frozenset(
            {"tenant_id", "close_id", "proposed_entry_id", "ledger_snapshot_id"}
            | {"external_txn_id", "match_rule"}
        ),
    }
)
# Set-once (trigger `closes_set_once`) or forward-only (`analytic_line_forward`) columns.
UPDATE_COLUMNS.update(
    {
        "reconciling_items": frozenset({"issue_id", "proposed_entry_id"}),
        "analytic_lines": frozenset({"status"}),
        "analytic_explanations": frozenset({"accepted_by", "accepted_actor_kind", "accepted_at"}),
        "close_entry_recordings": frozenset({"confirmed_by", "confirmed_at"}),
    }
)

# C-02-T16 (0965, DEC-5620).
C02T16_TABLES: frozenset[str] = frozenset(
    {
        "close_deliverable_versions",
        "close_deliverables",
        "close_reopenings",
        "tax_handoffs",
    }
)
_S50_INSERT_ONLY_1: frozenset[str] = frozenset(
    {
        "close_deliverable_versions",
        "close_reopenings",
        "tax_handoffs",
    }
)
INSERT_COLUMNS["close_deliverables"] = frozenset(
    {
        "close_id",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["close_deliverables"] = frozenset(
    {
        "c10_deliverable_ref",
        "c18_approval_ref",
        "client_approved_at",
        "client_approved_by_contact_id",
        "current_version_no",
        "released_at",
        "released_by",
        "status",
    }
)
INSERT_COLUMNS["close_deliverable_versions"] = frozenset(
    {
        "cas_answer",
        "commentary",
        "content_hash",
        "deliverable_id",
        "generated_document_ids",
        "legend_key",
        "posted_tb_ref",
        "route",
        "run_id",
        "sections",
        "ssars_settings_version_id",
        "studio_version",
        "tenant_id",
        "version_no",
    }
)
INSERT_COLUMNS["close_reopenings"] = frozenset(
    {
        "close_id",
        "reason",
        "reopened_by",
        "tenant_id",
    }
)
INSERT_COLUMNS["tax_handoffs"] = frozenset(
    {
        "c12_ref",
        "client_entity_id",
        "close_id",
        "created_tax_issue_ids",
        "engine",
        "handed_off_by",
        "items",
        "schedules",
        "supersedes_id",
        "target_tax_return_id",
        "tb_snapshot_id",
        "tenant_id",
        "version_no",
    }
)

# The tables this module owns and its insert-only tables, after S50 (one definition each).
_TABLES_PRE_S53: frozenset[str] = _TABLES_PRE_S50 | C02T16_TABLES
_INSERT_ONLY_PRE_S53: frozenset[str] = _INSERT_ONLY_PRE_S50 | _S50_INSERT_ONLY_1

# C-02-T38 (1013, TASK-8904): information returns; TINs sealed (ADR-167)
_TABLES_S53_1: frozenset[str] = frozenset(
    {
        "backup_withholding_events",
        "information_return_batches",
        "information_returns",
        "tin_match_results",
        "vendor_payment_rollups",
        "vendors_1099",
        "w9_requests",
    }
)
_INSERT_ONLY_S53_1: frozenset[str] = frozenset(
    {"backup_withholding_events", "information_returns", "tin_match_results", "w9_requests"}
)
INSERT_COLUMNS["backup_withholding_events"] = frozenset(
    {
        "event",
        "evidence_version_id",
        "notice_received_on",
        "rate_percent",
        "reason",
        "recorded_by",
        "tenant_id",
        "vendor_id",
    }
)
INSERT_COLUMNS["information_return_batches"] = frozenset(
    {"client_entity_id", "due_on", "id", "tax_year", "tenant_id"}
)
UPDATE_COLUMNS["information_return_batches"] = frozenset(
    {
        "ack_at",
        "ack_evidence_version_id",
        "ack_recorded_by",
        "approved_at",
        "approved_by",
        "due_on",
        "exported_at",
        "exported_by",
        "filed_at",
        "filed_evidence_version_id",
        "filed_on",
        "filed_recorded_by",
        "iris_file_document_id",
        "iris_file_sha256",
        "iris_receipt_id",
        "status",
        "version",
    }
)
INSERT_COLUMNS["information_returns"] = frozenset(
    {"amount", "batch_id", "box", "form", "tenant_id", "threshold_ref", "vendor_id"}
)
INSERT_COLUMNS["tin_match_results"] = frozenset(
    {"checked_on", "evidence_version_id", "recorded_by", "result", "tenant_id", "vendor_id"}
)
INSERT_COLUMNS["vendor_payment_rollups"] = frozenset(
    {
        "amount",
        "client_entity_id",
        "method",
        "source_snapshot_id",
        "tax_year",
        "tenant_id",
        "txn_count",
        "vendor_id",
    }
)
UPDATE_COLUMNS["vendor_payment_rollups"] = frozenset(
    {"amount", "computed_at", "source_snapshot_id", "txn_count"}
)
INSERT_COLUMNS["vendors_1099"] = frozenset(
    {
        "client_entity_id",
        "display_name",
        "entity_type",
        "entity_type_source",
        "external_vendor_id",
        "id",
        "is_attorney",
        "tenant_id",
    }
)
UPDATE_COLUMNS["vendors_1099"] = frozenset(
    {
        "backup_withholding",
        "display_name",
        "entity_type",
        "entity_type_source",
        "exempt_reason",
        "is_attorney",
        "tin_fingerprint",
        "tin_kind",
        "tin_last4",
        "tin_sealed",
        "updated_at",
        "updated_by",
        "version",
        "w9_evidence_version_id",
        "w9_signed_on",
        "w9_status",
    }
)
INSERT_COLUMNS["w9_requests"] = frozenset(
    {
        "channel",
        "client_entity_id",
        "id",
        "request_item_ids",
        "sent_by",
        "tenant_id",
        "vendor_ids",
        "wording_template_version_id",
    }
)

# The tables this module owns and its insert-only tables after S53 (one definition each).
TABLES: frozenset[str] = _TABLES_PRE_S53 | _TABLES_S53_1
INSERT_ONLY: frozenset[str] = _INSERT_ONLY_PRE_S53 | _INSERT_ONLY_S53_1
