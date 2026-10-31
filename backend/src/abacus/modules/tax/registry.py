"""The tax module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. Empty until its first table.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {"tax_returns"}  # F-03-T22 (0089)
    | {"tax_return_status_events", "return_engine_summaries"}  # T-02-T07 (0403)
    | {"engine_return_links", "engine_sync_events"}  # T-01-T19 (0465)
    | {"engine_import_diffs", "engine_diagnostics"}  # T-01-T19 (0465)
    # T-01-T43 (0550, DEC-1651): CLI-05's tax profile.
    | {"tax_profile_files", "tax_authorizations", "tax_elections"}
    | {"transcripts", "transcript_lines", "transcript_comparisons"}
    | {"write_operations", "engine_exports"}  # T-01-T25 (0561, DEC-1462)
    | {"engine_acks"}  # T-01-T26 (0562, DEC-1464)
)
# T-02-T07 (0403): `tax_returns` takes updates of its v1 columns now, so it is no longer
# insert-only; its events and engine summaries are.
INSERT_ONLY: frozenset[str] = frozenset(
    {"tax_return_status_events", "return_engine_summaries", "engine_sync_events"}
    | {"transcripts", "transcript_lines", "transcript_comparisons"}  # T-01-T43 (0550)
    | {"write_operations"}  # T-01-T25 (0561): one row per write, a grant consumed once
    | {"engine_acks"}  # T-01-T26 (0562): the e-file status report, as received
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
# T-01-T43 (0550, DEC-1651): CLI-05's tax profile.
INSERT_COLUMNS["tax_profile_files"] = frozenset(
    {"id", "tenant_id", "client_entity_id", "uploaded_by", "file_name", "media_type"}
    | {"size_bytes", "sha256", "storage_key", "storage_version_id"}
)
INSERT_COLUMNS["tax_authorizations"] = frozenset(
    {"id", "tenant_id", "client_entity_id", "form", "state_form_code", "designees"}
    | {"tax_matters", "forms_covered", "tax_years", "received_on", "expires_on", "status"}
    | {"envelope_id", "evidence_version_id", "created_by"}
)
INSERT_COLUMNS["tax_elections"] = frozenset(
    {"id", "tenant_id", "client_entity_id", "kind", "jurisdiction", "tax_year", "amount"}
    | {"status_code", "decided_by_return_id", "updated_by"}
)
INSERT_COLUMNS["transcripts"] = frozenset(
    {"id", "tenant_id", "client_entity_id", "kind", "tax_year", "pulled_at", "pulled_by"}
    | {"authorization_id", "evidence_version_id", "file_id", "parse_status", "problems"}
    | {"account_balance"}
)
INSERT_COLUMNS["transcript_lines"] = frozenset(
    {"tenant_id", "transcript_id", "line_no", "form", "payer_name", "amount", "tc_code"}
    | {"tc_date"}
)
INSERT_COLUMNS["transcript_comparisons"] = frozenset(
    {"id", "tenant_id", "transcript_id", "return_id", "checkpoint_id", "result"}
    | {"difference_total", "lines", "agreeing", "engine_version", "computed_by"}
)
INSERT_COLUMNS["write_operations"] = frozenset(
    {"id", "tenant_id", "capability", "subject_type", "subject_id", "grant_id"}
    | {"payload_sha256", "performed_by"}
)
INSERT_COLUMNS["engine_exports"] = frozenset(
    {"id", "tenant_id", "return_id", "checkpoint_id", "content_hash", "engine_return_id"}
    | {"version", "file_name", "file_key", "file_version", "file_size", "sha256"}
    | {"write_operation_id", "generated_by"}
)
INSERT_COLUMNS["engine_acks"] = frozenset(
    {"tenant_id", "return_id", "sync_event_id", "jurisdiction", "submission_last4", "status"}
    | {"status_at", "reject_code", "reject_text"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "engine_exports": frozenset({"marked_exported_at", "marked_exported_by", "row_version"}),
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
    # T-01-T43 (0550): the file's consumer (once), an authorization's status, an election.
    "tax_profile_files": frozenset({"consumed_by"}),
    "tax_authorizations": frozenset(
        {"status", "envelope_id", "evidence_version_id", "row_version"}
    ),
    "tax_elections": frozenset(
        {"amount", "status_code", "decided_by_return_id", "updated_by", "row_version"}
    ),
}
