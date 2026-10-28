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
        "statement_datasets",  # SPEC-312 (TASK-324)
        "statement_transactions",
        # P-03-T04 (0109): the trust kit, every table insert-only.
        "evidence_derivations",
        "citations",
        "citation_events",
        "evidence_pages",
        "pii_scan_runs",
        "pii_regions",
        "pii_reveals",
        # Q-02-T23 (0112): retention. Floors and defaults are global, definers only.
        "retention_floors",
        "retention_policy_defaults",
        "retention_policies",
        "retention_policy_versions",
        # Q-02-T29 (0126): legal holds and their reference-counted objects.
        "legal_holds",
        "hold_objects",
        # P-06-T18 (0144; ADR-162): detached keys and client withdrawals.
        "evidence_object_keys",
        "evidence_withdrawals",
        "evidence_version_voids",  # R-01 Story 2.2 (0159): retired with its voided rule link
        # A-01-T18 (0191): engagement exports, their downloads and their contents.
        "engagement_exports",
        "engagement_export_downloads",
        "engagement_export_contents",
        "firm_export_schedules",  # G-02-T19 (0241): the firm export's monthly schedule
        # Q-02-T43 (0216): firm exports with dual approval and their 15-minute links.
        "firm_exports",
        "firm_export_links",
        "firm_export_downloads",
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
        "statement_datasets",  # SPEC-312 (TASK-324): an approval, as approved
        "statement_transactions",
        "evidence_derivations",  # P-03-T04
        "citations",  # P-03-T04
        "citation_events",  # P-03-T04
        "evidence_pages",  # P-03-T04
        "pii_scan_runs",  # P-03-T04
        "pii_regions",  # P-03-T04
        "pii_reveals",  # P-03-T04
        "retention_policy_versions",  # Q-02-T23: written by the policy trigger only
        "evidence_version_voids",  # R-01 Story 2.2 (0159)
        "engagement_export_downloads",  # A-01-T18 (0191)
        "engagement_export_contents",  # A-01-T18 (0191)
        "firm_export_links",  # Q-02-T43 (0216)
        "firm_export_downloads",  # Q-02-T43 (0216)
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # G-02-T19 (0241): a live person's schedule (the trigger clears approvals on insert).
    "firm_export_schedules": frozenset(
        {"tenant_id", "time_zone", "contents", "paused", "status", "updated_by"}
    ),
    "evidence_items": frozenset(
        {"id", "tenant_id", "engagement_id", "title", "created_by_kind", "created_by_id"}
        # N-01-T06 (0270, ADR-158): the scope columns; a trigger fills them from the engagement.
        | {"client_id", "work_item_id", "scope", "folder_kind"}
    ),
    "evidence_versions": frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_item_id", "version_no", "fingerprint"}
        | {"storage_key", "storage_version_id", "size_bytes", "media_type", "source", "method"}
        | {"pulled_at", "period_start", "period_end", "client_entity_id", "snapshot_id"}
        | {"idempotency_key"}
        | {"upload_note"}  # SPEC-023: written once, at insert
        | {"storage_mode"}  # P-06-T18 (0144): detached-key client uploads, at insert
        # N-01-T06 (0270, ADR-158): channel, supersede link and virtual splits, at insert.
        | {"channel", "supersedes_version_id", "parent_version_id", "page_range"}
        | {"virtual_label", "virtual_amount", "display_name", "classification_id"}
    ),
    # P-06-T18 (0144): a detached-key version's wrapped data key, with its version.
    "evidence_object_keys": frozenset(
        {"tenant_id", "evidence_version_id", "key_id", "wrapped_key"}
    ),
    # P-06-T19 (0144): the client's withdrawal; the trigger binds the person.
    "evidence_withdrawals": frozenset(
        {"tenant_id", "evidence_version_id", "engagement_id", "request_item_id"}
        | {"withdrawn_by_user_id", "withdrawn_at", "erase_after"}
    ),
    # R-01 Story 2.2 (0159): a version retired with its voided rule link; the trigger binds it.
    "evidence_version_voids": frozenset(
        {"tenant_id", "evidence_version_id", "engagement_id", "fulfilment_id", "voided_by"}
    ),
    # SPEC-023 (TASK-039): files dropped at the engagement level, waiting to be matched.
    "inbox_files": frozenset(
        {"tenant_id", "engagement_id", "file_name", "media_type", "size_bytes", "fingerprint"}
        | {"storage_key", "storage_version_id", "uploaded_by", "uploaded_by_staff", "note"}
        # R-01-T09 (0153): a portal drop.
        | {"channel", "drop_batch_id", "drop_binder_id", "drop_key", "duplicate_of_version_id"}
    ),
    "review_decisions": frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_version_id", "request_item_id"}
        | {"decision", "reason_code", "note", "screening_result_id", "corrects_proposal"}
        | {"actor_kind", "actor_id"}
        | {"decision_seq", "undoes_decision_id"}  # P-01-T13 (0117)
        | {"prior_assignee_user_id", "prior_item_statuses"}
    ),
    "review_assignments": frozenset(
        {"tenant_id", "evidence_version_id", "engagement_id", "assignee_user_id"} | {"assigned_by"}
    ),
    # SPEC-312 (TASK-324): approved statement transactions.
    "statement_datasets": frozenset(
        {"tenant_id", "engagement_id", "request_item_id", "evidence_version_id", "format"}
        | {"account_kind", "issuer", "last4", "period_start", "period_end", "opening", "closing"}
        | {"opening_source", "closing_source", "included_total", "line_count", "excluded_count"}
        | {"signs_flipped", "approved_by", "actor_kind"}
        | {"field_sources"}  # TASK-334
    ),
    "statement_transactions": frozenset(
        {"tenant_id", "dataset_id", "position", "posted_on", "description", "amount", "page"}
        | {"excluded", "exclusion_reason"}
        | {"box"}  # TASK-334
    ),
    # A-01-T18 (0191): a person's export request; status starts queued (the default).
    "engagement_exports": frozenset(
        {"id", "tenant_id", "engagement_id", "work_item_id", "client_id", "kind", "scope"}
        | {"format_version", "requested_by", "requested_by_kind", "mfa_at", "grant_id"}
        | {"not_before"}
    ),
    "engagement_export_downloads": frozenset(
        {"tenant_id", "export_id", "user_id", "bytes_sent", "range_start", "range_end", "mfa_at"}
    ),
    "engagement_export_contents": frozenset({"tenant_id", "export_id", "evidence_version_id"}),
    # Q-02-T43 (0216): the request; status starts awaiting_approval (the default).
    "firm_exports": frozenset(
        {"id", "tenant_id", "scope", "origin", "requested_by", "requested_by_kind"}
        | {"request_mfa_at", "approver_id"}
    ),
    "firm_export_links": frozenset(
        {"id", "tenant_id", "export_id", "user_id", "expires_at", "mfa_at"}
    ),
    "firm_export_downloads": frozenset(
        {"tenant_id", "export_id", "link_id", "user_id", "bytes_sent", "range_start"}
        | {"range_end", "mfa_at"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # G-02-T19 (0241): set and approved in place against `version`; never deleted.
    "firm_export_schedules": frozenset(
        {"time_zone", "contents", "paused", "status", "approved_security_by"}
        | {"approved_partner_by", "version", "updated_by", "updated_at"}
    ),
    "inbox_files": frozenset(  # SPEC-023: assigned or discarded, once
        {"status", "assigned_item_id", "assigned_version_id", "decided_by", "decided_at"}
        | {"sort_outcome"}  # R-01-T09 (0153): once, from NULL (trigger)
    ),
    "review_assignments": frozenset({"assignee_user_id", "assigned_by", "assigned_at"}),
    "retention_policies": frozenset(  # Q-02-T23: version and history are the trigger's
        {"firm_years", "clock_start_event", "lock", "basis", "updated_by", "updated_at"}
    ),
    # Q-02-T29: status forward only; `released_by` bound to the session's person (trigger).
    "legal_holds": frozenset(
        {"status", "applied_at", "released_by", "released_at", "release_reason"}
    ),
    "hold_objects": frozenset({"applied_at", "released_at"}),  # each stamped once
    # P-06-T18 (0144): acceptance retains the key, one-way (the guard); erase is the definer's.
    "evidence_object_keys": frozenset({"retained_at"}),
    # P-06-T19 (0144): the purge's stamps only (the guard binds the purge's system actor).
    "evidence_withdrawals": frozenset({"erased_at", "erase_blocked_at", "block_reason"}),
    # A-01-T18 (0191): status forward only and the stamps (the guard trigger).
    "engagement_exports": frozenset(
        {"status", "as_of_seq", "bundle_sha256", "manifest_sha256", "bytes", "file_count"}
        | {"request_count", "segment_count", "object_prefix", "ready_at", "expires_at"}
        | {"failure_code", "void_reason", "undone_at", "undone_by"}
    ),
    # Q-02-T43 (0216): status forward only, the decision bound to the named approver and the
    # stamps written once (the guard trigger).
    "firm_exports": frozenset(
        {"status", "decided_by", "decided_at", "decided_mfa_at", "decline_reason"}
        | {"bundle_sha256", "manifest_sha256", "bytes", "segment_count", "object_prefix"}
        | {"ready_at", "available_until", "downloaded_at", "failure_code"}
    ),
}
