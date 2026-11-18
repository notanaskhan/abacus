"""The tax module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. Empty until its first table.
"""

from __future__ import annotations

_TABLES_0720: frozenset[str] = frozenset(
    {"tax_returns"}  # F-03-T22 (0089)
    | {"tax_return_status_events", "return_engine_summaries"}  # T-02-T07 (0403)
    | {"engine_return_links", "engine_sync_events"}  # T-01-T19 (0465)
    | {"engine_import_diffs", "engine_diagnostics"}  # T-01-T19 (0465)
    # T-01-T43 (0550, DEC-1651): CLI-05's tax profile.
    | {"tax_profile_files", "tax_authorizations", "tax_elections"}
    | {"transcripts", "transcript_lines", "transcript_comparisons"}
    | {"write_operations", "engine_exports"}  # T-01-T25 (0561, DEC-1462)
    | {"engine_acks"}  # T-01-T26 (0562, DEC-1464)
    # T-02-T20 (0565, DEC-1471): K-1 packages.
    | {"k1_recipients", "k1_packages", "k1_package_events", "k1_documents", "k1_box_lines"}
    | {"k1_handoffs", "recipient_details_changes"}
    | {"k1_releases", "k1_release_deliveries"}  # T-02-T21 (0566, DEC-1476): the release
    | {"delivery_packets"}  # T-01-T35 (0523, DEC-1565)
    | {"efile_amount_bindings"}  # T-01-T36 (0524, DEC-1566)
    | {"transmissions", "efile_acks"}  # T-01-T37 (0568, DEC-1570)
    | {"filed_return_deliveries"}  # T-01-T41 (0569, DEC-1571)
    | {"k1_furnishing_disclosures"}  # S20e (0590, DEC-1579): the e-furnishing disclosure
    # T-03-T03 (0655, DEC-2202): extensions and estimates.
    | {"filing_extensions", "extension_payments", "estimate_schedules", "estimate_installments"}
)
# T-02-T07 (0403): `tax_returns` takes updates of its v1 columns now, so it is no longer
# insert-only; its events and engine summaries are.
_INSERT_ONLY_0720: frozenset[str] = frozenset(
    {"tax_return_status_events", "return_engine_summaries", "engine_sync_events"}
    | {"transcripts", "transcript_lines", "transcript_comparisons"}  # T-01-T43 (0550)
    | {"write_operations"}  # T-01-T25 (0561): one row per write, a grant consumed once
    | {"engine_acks"}  # T-01-T26 (0562): the e-file status report, as received
    | {"transmissions", "efile_acks"}  # T-01-T37 (0568): the ERO's record and the acks
    | {"filed_return_deliveries"}  # T-01-T41 (0569): a release, never changed
    | {"k1_furnishing_disclosures"}  # S20e (0590): a version, never changed
    | {"k1_package_events", "k1_documents", "k1_box_lines"}  # T-02-T20 (0565)
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
INSERT_COLUMNS["delivery_packets"] = frozenset(
    {"id", "tenant_id", "return_id", "version", "items", "letter_document_id", "prepared_by"}
)
INSERT_COLUMNS["efile_amount_bindings"] = frozenset(
    {"id", "tenant_id", "return_id", "envelope_id", "checkpoint_id", "figures", "figures_sha256"}
    | {"tolerances_ref"}
)
INSERT_COLUMNS["transmissions"] = frozenset(
    {"id", "tenant_id", "return_id", "binding_id", "envelope_id", "ero_user_id", "method"}
    | {"jurisdictions", "transmitted_on", "recorded_by", "actor_kind"}
)
INSERT_COLUMNS["efile_acks"] = frozenset(
    {"id", "tenant_id", "return_id", "transmission_id", "jurisdiction", "status"}
    | {"submission_id_last4", "reject_code", "reject_text", "received_at", "source"}
    | {"engine_ack_id", "evidence_version_id", "recorded_by"}
)
INSERT_COLUMNS["filed_return_deliveries"] = frozenset(
    {"id", "tenant_id", "return_id", "engagement_id", "client_id", "packet_id"}
    | {"evidence_version_id", "published_by", "actor_kind"}
)
INSERT_COLUMNS["k1_furnishing_disclosures"] = frozenset(
    {"id", "tenant_id", "version_no", "body", "body_sha256", "imported_by"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # T-01-T36 (0524): superseded once, never cleared (the system relocks, never unlocks).
    "efile_amount_bindings": frozenset({"superseded_at", "superseded_reason"}),
    # T-01-T35 (0523): a draft's items and letter; status forward (a guard trigger), the approver.
    "delivery_packets": frozenset(
        {"items", "letter_document_id", "status", "approved_by", "approved_at", "row_version"}
    ),
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
    # T-02-T20 (0565): what a recipient, package, hand-off or details change may change.
    "k1_recipients": frozenset(
        {"display_name", "recipient_kind", "is_entity", "tin_last4", "tin_kind", "address"}
        | {"ownership_note", "contact_id"}  # T-02-T21 (0566): the contact delivered to
    ),
    "k1_packages": frozenset(
        {"status", "delivery_contact_id", "e_furnishing_consent", "released_at"}  # + 0566
        | {"partner_id"}  # T-05-T17 (0821): which partner a draft K-1 is for
    ),
    "k1_handoffs": frozenset(
        {"status", "replaced_at", "final_values", "target_evidence_version_id"}
        | {"target_request_item_id"}
    ),
    "recipient_details_changes": frozenset({"status", "decided_by", "decided_at", "reason"}),
    # T-02-T21 (0566): a release changes only its status; the ledger stamps each step once.
    "k1_releases": frozenset(
        {"status", "undone_at", "undone_by", "started_at", "completed_at", "failure_code"}
    ),
    "k1_release_deliveries": frozenset(
        {"contact_id", "access_grant_id", "invitation_id", "access_at", "released_at"}
        | {"message_id", "emailed_at", "handoffs_at"}
    ),
}

# T-03-T03 (0655, DEC-2202): extensions and estimates. An approved extension payment is frozen by
# its trigger (a change supersedes it); the rest take their computed and recorded columns.
INSERT_COLUMNS["filing_extensions"] = frozenset(
    {"id", "tenant_id", "engagement_id", "work_item_id", "tax_return_id", "tax_year"}
    | {"jurisdiction", "form", "status", "likely_to_extend", "likely_reasons", "likely_note"}
    | {"original_due_on", "extended_due_on", "due_rules_version_id", "projected_liability"}
    | {"projected_liability_source", "projected_liability_ref", "withholding_plus_estimates"}
    | {"safe_harbor_pct", "safe_harbor_target", "engine_version", "inputs_hash", "created_by"}
)
INSERT_COLUMNS["extension_payments"] = frozenset(
    {"id", "tenant_id", "filing_extension_id", "kind", "amount", "paid_on", "proposed_by"}
    | {"supersedes_id"}
)
INSERT_COLUMNS["estimate_schedules"] = frozenset(
    {"id", "tenant_id", "client_entity_id", "basis_tax_return_id", "tax_year", "jurisdiction"}
    | {"form", "method", "prior_year_tax", "prior_year_tax_ref", "prior_agi_over_threshold"}
    | {"projected_withholding", "annual_required", "engine_version", "inputs_hash"}
    | {"payment_method_label", "created_by"}
)
INSERT_COLUMNS["estimate_installments"] = frozenset(
    {"id", "tenant_id", "schedule_id", "quarter", "due_on", "due_rules_version_id", "amount"}
    | {"status"}
)
UPDATE_COLUMNS["filing_extensions"] = frozenset(
    {"status", "likely_to_extend", "likely_reasons", "likely_note", "original_due_on"}
    | {"extended_due_on", "due_rules_version_id", "filed_on", "filed_recorded_by", "form"}
    | {"filed_form_evidence_version_id", "ack_received_at", "reject_code"}
    | {"projected_liability", "projected_liability_source", "projected_liability_ref"}
    | {"withholding_plus_estimates", "safe_harbor_pct", "safe_harbor_target"}
    | {"engine_version", "inputs_hash", "row_version", "confirmation_request_item_id"}
)
UPDATE_COLUMNS["extension_payments"] = frozenset(
    {"approved_by", "approved_actor_kind", "approved_at", "paid_on"}
    | {"confirmation_evidence_version_id"}
)
UPDATE_COLUMNS["estimate_schedules"] = frozenset(
    {"method", "prior_year_tax", "prior_year_tax_ref", "prior_agi_over_threshold"}
    | {"projected_withholding", "annual_required", "engine_version", "inputs_hash"}
    | {"payment_method_label", "row_version"}
)
UPDATE_COLUMNS["estimate_installments"] = frozenset(
    {"due_on", "due_rules_version_id", "amount", "status", "scheduled_for", "paid_on"}
    | {"confirmation_request_item_id", "confirmed_by_contact_id", "confirmed_at", "row_version"}
    | {"paid_evidence_version_id"}
)

# T-04-T10 (0761, DEC-3123): the individual return workspace.
_TABLES_0761: frozenset[str] = _TABLES_0720 | frozenset(
    {
        "return_worksheets",
        "return_worksheet_sections",
        "return_fields",
        "document_approvals",
        "k1_activities",
        "k1_treatments",
        "k1_treatment_events",
        "residency_determinations",
        "residency_facts",
    }
)
_INSERT_ONLY_0761: frozenset[str] = _INSERT_ONLY_0720 | frozenset(
    {"document_approvals", "k1_treatment_events", "residency_facts"}
)
INSERT_COLUMNS.update(
    {
        "return_worksheets": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "id",
                "key",
                "form_code",
                "title",
                "group_path",
                "jurisdiction",
                "default_tsj",
                "origin",
                "new_vs_prior_year",
                "k1_activity_id",
                "sort_order",
                "footer_note",
                "active",
                "created_in_checkpoint_id",
                "content_hash",
            }
        ),
        "return_worksheet_sections": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "id",
                "worksheet_id",
                "key",
                "name",
                "sort_order",
                "content_hash",
            }
        ),
        "return_fields": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "id",
                "worksheet_id",
                "section_id",
                "field_key",
                "line_ref",
                "label",
                "tsj",
                "value_type",
                "derivation",
                "formula_ref",
                "engine_field_key",
                "estimate_flag",
                "new_this_year_note",
                "current_value",
                "current_fvv_seq",
                "sort_order",
            }
        ),
        "document_approvals": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "evidence_version_id",
                "level",
                "kind",
                "reverses_id",
                "actor_user_id",
                "function_at_time",
                "reason_sealed",
                "seen_version",
            }
        ),
        "k1_activities": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "id",
                "issuer_name",
                "issuer_client_entity_id",
                "issuer_form",
                "recipient_tsj",
                "ownership_pct",
                "source_package_id",
                "k1_state",
                "released_at",
                "source_evidence_version_ids",
                "k1_worksheet_id",
                "content_hash",
            }
        ),
        "k1_treatments": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "id",
                "k1_activity_id",
                "kind",
                "resolved",
                "prior_year",
                "changed_vs_prior",
                "status",
                "proposal_id",
                "engine_name",
                "engine_version",
                "inputs_hash",
            }
        ),
        "k1_treatment_events": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "treatment_id",
                "event",
                "actor_kind",
                "actor_id",
                "proposal_id",
                "reason_sealed",
            }
        ),
        "residency_determinations": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "id",
                "scope",
                "jurisdictions",
                "options",
                "proposed_option",
                "recommended_by_run_id",
                "status",
                "conflict",
                "proposal_id",
            }
        ),
        "residency_facts": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "tax_return_id",
                "determination_id",
                "fact_key",
                "value",
                "citation_ids",
                "source_kind",
                "added_by_kind",
            }
        ),
    }
)
UPDATE_COLUMNS.update(
    {
        "return_worksheets": frozenset(
            {
                "title",
                "group_path",
                "footer_note",
                "active",
                "sort_order",
                "content_hash",
                "version_no",
                "updated_at",
            }
        ),
        "return_worksheet_sections": frozenset(
            {"name", "sort_order", "content_hash", "version_no", "updated_at"}
        ),
        "return_fields": frozenset(
            {
                "label",
                "estimate_flag",
                "new_this_year_note",
                "current_value",
                "current_fvv_seq",
                "sort_order",
                "updated_at",
            }
        ),
        "k1_activities": frozenset(
            {
                "k1_state",
                "released_at",
                "source_evidence_version_ids",
                "k1_worksheet_id",
                "content_hash",
                "version_no",
                "updated_at",
            }
        ),
        "k1_treatments": frozenset(
            {
                "resolved",
                "prior_year",
                "changed_vs_prior",
                "status",
                "override_value",
                "override_reason_sealed",
                "decided_by",
                "decided_at",
                "proposal_id",
                "checkpoint_id",
                "follow_up_note",
                "engine_name",
                "engine_version",
                "inputs_hash",
                "version_no",
                "updated_at",
            }
        ),
        "residency_determinations": frozenset(
            {
                "jurisdictions",
                "options",
                "proposed_option",
                "recommended_by_run_id",
                "status",
                "conflict",
                "confirmed_by",
                "confirmed_at",
                "proposal_id",
                "checkpoint_id",
                "issue_id",
                "version_no",
                "updated_at",
            }
        ),
    }
)

# T-05-T17 (0821, DEC-4304): the entity return core (runs dark until the T-05 services).
_TABLES_0821: frozenset[str] = _TABLES_0761 | frozenset(
    {
        "entity_return_profiles",
        "partners",
        "ownership_periods",
        "interest_transfers",
        "allocation_structures",
        "allocation_rungs",
        "allocation_results",
    }
)
_INSERT_ONLY_0821: frozenset[str] = _INSERT_ONLY_0761 | frozenset(
    {"allocation_structures", "allocation_results"}
)
INSERT_COLUMNS.update(
    {
        "entity_return_profiles": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "id",
                "principal_activity",
                "business_code",
                "accounting_method",
                "books_basis",
                "partnership_representative_contact_id",
                "designated_individual_contact_id",
                "ledger_source",
                "prior_year_return_id",
            }
        ),
        "partners": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "id",
                "kind",
                "display_name",
                "entity_kind",
                "admitted_on",
                "withdrawn_on",
                "related_client_entity_id",
                "portal_contact_id",
                "ord",
            }
        ),
        "ownership_periods": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "id",
                "partner_id",
                "period_from",
                "period_to",
                "profit_pct",
                "loss_pct",
                "capital_pct",
            }
        ),
        "interest_transfers": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "id",
                "transfer_date",
                "from_partner_id",
                "to_partner_id",
                "points",
                "price",
                "citation_ids",
            }
        ),
        "allocation_structures": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "id",
                "version_no",
                "status",
                "kind",
                "method",
                "convention",
                "income_to_allocate",
                "distributable",
                "proposed_by_kind",
                "proposal_id",
                "content_hash",
                "engine_name",
                "engine_version",
                "inputs_hash",
                "citation_ids",
                "supersedes_id",
            }
        ),
        "allocation_rungs": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "id",
                "structure_id",
                "priority",
                "rule_type",
                "params",
            }
        ),
        "allocation_results": frozenset(
            {
                "tenant_id",
                "engagement_id",
                "work_item_id",
                "structure_id",
                "partner_id",
                "period_key",
                "rung_priority",
                "amount",
            }
        ),
    }
)
UPDATE_COLUMNS.update(
    {
        "entity_return_profiles": frozenset(
            {
                "principal_activity",
                "business_code",
                "accounting_method",
                "books_basis",
                "partnership_representative_contact_id",
                "designated_individual_contact_id",
                "ledger_source",
                "prior_year_return_id",
                "version_no",
                "updated_at",
            }
        ),
        "partners": frozenset(
            {
                "kind",
                "display_name",
                "entity_kind",
                "admitted_on",
                "withdrawn_on",
                "related_client_entity_id",
                "portal_contact_id",
                "ord",
                "updated_at",
            }
        ),
        "ownership_periods": frozenset(
            {"period_from", "period_to", "profit_pct", "loss_pct", "capital_pct"}
        ),
        "interest_transfers": frozenset({"transfer_date", "points", "price", "citation_ids"}),
        "allocation_rungs": frozenset({"priority", "rule_type", "params"}),
    }
)

# T-05-T20 (0830, DEC-4403): the preparer memo and planning opportunities (dark until T-05-T48).
_TABLES_0830: frozenset[str] = _TABLES_0821 | frozenset(
    {"preparer_memos", "preparer_memo_versions", "preparer_memo_events", "planning_opportunities"}
)
_INSERT_ONLY_0830: frozenset[str] = _INSERT_ONLY_0821 | frozenset(
    {"preparer_memo_versions", "preparer_memo_events"}
)
_SCOPE_0830 = frozenset({"tenant_id", "engagement_id", "work_item_id"})
INSERT_COLUMNS.update(
    {
        "preparer_memos": _SCOPE_0830
        | frozenset(
            {
                "id",
                "workpaper_id",
                "current_version_no",
                "figure_fingerprint",
                "drafted_run_id",
                "content_hash",
            }
        ),
        "preparer_memo_versions": _SCOPE_0830
        | frozenset(
            {
                "memo_id",
                "version_no",
                "sections",
                "cause",
                "created_by_kind",
                "agent_run_id",
                "on_behalf_of_user_id",
                "content_hash",
                "figure_fingerprint",
            }
        ),
        "preparer_memo_events": _SCOPE_0830 | frozenset({"memo_id", "event", "version_no", "ref"}),
        "planning_opportunities": _SCOPE_0830
        | frozenset({"id", "memo_id", "source_kind", "title", "body", "citation_ids"}),
    }
)
UPDATE_COLUMNS.update(
    {
        "preparer_memos": frozenset(
            {"current_version_no", "figure_fingerprint", "drafted_run_id", "content_hash"}
            | {"updated_at"}
        ),
        "planning_opportunities": frozenset({"title", "body", "citation_ids", "updated_at"}),
    }
)

# T-05-T22 (0831, DEC-4404): partner TINs (sealed, by column grant) and their reveals.
_TABLES_0831: frozenset[str] = _TABLES_0830 | frozenset({"partner_tin_reveals"})
_INSERT_ONLY_0831: frozenset[str] = _INSERT_ONLY_0830 | frozenset({"partner_tin_reveals"})
INSERT_COLUMNS["partners"] = INSERT_COLUMNS["partners"] | frozenset(
    {"tin_sealed", "tin_last4", "tin_kind"}
)
UPDATE_COLUMNS["partners"] = UPDATE_COLUMNS["partners"] | frozenset(
    {"tin_sealed", "tin_last4", "tin_kind"}
)
INSERT_COLUMNS["partner_tin_reveals"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "partner_id", "user_id", "reason_code"}
    | {"mfa_at"}
)


# T-05-T42 (0860, DEC-4705): workbook sections (stable sign-off targets) and the notes of
# sign-offs given while a tie-out was off (sealed).
# T-05-T51 (0870, DEC-4904): a person's sealed note when resolving an issue no approved fix closed.
_TABLES_0870: frozenset[str] = _TABLES_0831 | frozenset(
    {"tax_workbook_sections", "tax_section_acknowledgements", "tax_issue_resolution_notes"}
)
_INSERT_ONLY_0870: frozenset[str] = _INSERT_ONLY_0831 | frozenset(
    {"tax_workbook_sections", "tax_section_acknowledgements", "tax_issue_resolution_notes"}
)
INSERT_COLUMNS["tax_workbook_sections"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "key"}
)
INSERT_COLUMNS["tax_section_acknowledgements"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "section_id", "sign_off_id", "off_count"}
    | {"note_sealed", "note_sha256", "created_by"}
)

INSERT_COLUMNS["tax_issue_resolution_notes"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "issue_id", "note_sealed", "note_sha256"}
    | {"created_by"}
)


# T-07-T07 (0883, DEC-5010): fiduciary_core. Parents and versions are insert-only (the current
# version is the latest seq); trust profiles and interpretations update the columns below.
_FIDUCIARY_0883: frozenset[str] = frozenset(
    {
        "trust_profiles",
        "governing_instruments",
        "instrument_segmentations",
        "instrument_clauses",
        "instrument_interpretations",
        "instrument_determinations",
        "instrument_determination_versions",
        "fai_lines",
        "fai_line_versions",
        "trust_expenses",
        "trust_expense_versions",
        "trust_distributions",
        "trust_distribution_versions",
        "fai_dni_computations",
        "beneficiary_allocations",
        "sixty_five_day_elections",
    }
)
_TABLES: frozenset[str] = _TABLES_0870 | _FIDUCIARY_0883
_INSERT_ONLY: frozenset[str] = _INSERT_ONLY_0870 | frozenset(
    {
        "governing_instruments",
        "instrument_segmentations",
        "instrument_clauses",
        "instrument_determinations",
        "instrument_determination_versions",
        "fai_lines",
        "fai_line_versions",
        "trust_expenses",
        "trust_expense_versions",
        "trust_distributions",
        "trust_distribution_versions",
        "fai_dni_computations",
        "beneficiary_allocations",
        "sixty_five_day_elections",
    }
)
INSERT_COLUMNS["trust_profiles"] = frozenset(
    {
        "client_entity_id",
        "tenant_id",
        "fiduciary_kind",
        "agreement_date",
        "revocable",
        "irrevocable_since",
        "settlor_name_sealed",
        "settlor_died_year",
        "remainder_sealed",
        "residency_state",
        "residency_basis",
        "state_form",
        "created_by",
    }
)
INSERT_COLUMNS["governing_instruments"] = frozenset(
    {
        "tenant_id",
        "client_entity_id",
        "evidence_version_id",
        "supersedes_instrument_id",
        "attached_by",
    }
)
INSERT_COLUMNS["instrument_segmentations"] = frozenset(
    {
        "tenant_id",
        "instrument_id",
        "segmentation_version",
        "text_source",
        "status",
        "confidence",
        "clause_count",
        "layer_sha256",
    }
)
INSERT_COLUMNS["instrument_clauses"] = frozenset(
    {
        "tenant_id",
        "segmentation_id",
        "label",
        "heading",
        "ordinal",
        "parent_clause_id",
        "page_from",
        "page_to",
        "regions",
        "text_sha256",
        "marked_by",
    }
)
INSERT_COLUMNS["instrument_interpretations"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "instrument_id", "segmentation_id"}
)
INSERT_COLUMNS["instrument_determinations"] = frozenset({"tenant_id", "interpretation_id", "key"})
INSERT_COLUMNS["instrument_determination_versions"] = frozenset(
    {
        "tenant_id",
        "determination_id",
        "key",
        "seq",
        "value_code",
        "value_text_sealed",
        "rationale_ref",
        "citation_ids",
        "set_by_kind",
        "set_by_id",
        "reason_sealed",
        "suggestion_id",
    }
)
INSERT_COLUMNS["fai_lines"] = frozenset(
    {
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "kind",
        "parent_line_id",
        "description",
        "created_by",
    }
)
INSERT_COLUMNS["fai_line_versions"] = frozenset(
    {
        "tenant_id",
        "line_id",
        "seq",
        "amount",
        "citation_ids",
        "set_by_kind",
        "set_by_id",
        "reason_sealed",
    }
)
INSERT_COLUMNS["trust_expenses"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "kind", "created_by"}
)
INSERT_COLUMNS["trust_expense_versions"] = frozenset(
    {
        "tenant_id",
        "expense_id",
        "seq",
        "charged_to",
        "amount",
        "deductible",
        "clause_id",
        "citation_ids",
        "set_by_kind",
        "set_by_id",
        "reason_sealed",
    }
)
INSERT_COLUMNS["trust_distributions"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "beneficiary_contact_id", "created_by"}
)
INSERT_COLUMNS["trust_distribution_versions"] = frozenset(
    {
        "tenant_id",
        "distribution_id",
        "seq",
        "paid_on",
        "amount",
        "form",
        "source",
        "clause_id",
        "sixty_five_day_election_id",
        "set_by_kind",
        "set_by_id",
        "reason_sealed",
    }
)
INSERT_COLUMNS["fai_dni_computations"] = frozenset(
    {
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "version_no",
        "interpretation_hash",
        "inputs_hash",
        "engine_name",
        "engine_version",
        "parameter_set",
        "income_distribution_deduction",
        "outputs",
        "prior_computation_id",
        "content_hash",
    }
)
INSERT_COLUMNS["beneficiary_allocations"] = frozenset(
    {
        "tenant_id",
        "computation_id",
        "beneficiary_contact_id",
        "distributions",
        "share",
        "dni_allocated",
        "box_1",
        "box_2a",
        "box_2b",
        "box_other",
    }
)
INSERT_COLUMNS["sixty_five_day_elections"] = frozenset(
    {
        "tenant_id",
        "client_entity_id",
        "tax_year",
        "seq",
        "status",
        "amount",
        "paid_on",
        "window_end",
        "decision_owner_contact_id",
        "recorded_by_user_id",
        "recorded_on_return_id",
        "evidence_version_id",
        "actor_kind",
    }
)
UPDATE_COLUMNS["trust_profiles"] = frozenset(
    {
        "agreement_date",
        "revocable",
        "irrevocable_since",
        "settlor_name_sealed",
        "settlor_died_year",
        "remainder_sealed",
        "residency_state",
        "residency_basis",
        "state_form",
        "row_version",
    }
)
UPDATE_COLUMNS["instrument_interpretations"] = frozenset(
    {
        "status",
        "scenario",
        "read_run_id",
        "version_no",
        "content_hash",
        "locked_at",
        "reopen_reason_sealed",
        "superseded_at",
        "row_version",
    }
)

# S46: T-07-T22 (0892) estate workpapers.
_TABLES_BEFORE_S49: frozenset[str] = _TABLES | frozenset(
    {
        "estate_computations",
        "estate_deduction_versions",
        "estate_deductions",
        "estate_inventory_item_versions",
        "estate_inventory_items",
        "estate_profiles",
        "gift_history_item_versions",
        "gift_history_items",
    }
)
_INSERT_ONLY_BEFORE_S49: frozenset[str] = _INSERT_ONLY | frozenset(
    {
        "estate_computations",
        "estate_deduction_versions",
        "estate_deductions",
        "estate_inventory_item_versions",
        "estate_inventory_items",
        "gift_history_item_versions",
        "gift_history_items",
    }
)
INSERT_COLUMNS["estate_computations"] = frozenset(
    {
        "content_hash",
        "engagement_id",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "label",
        "outputs",
        "parameter_set",
        "prior_computation_id",
        "tenant_id",
        "version_no",
        "work_item_id",
    }
)
INSERT_COLUMNS["estate_deduction_versions"] = frozenset(
    {
        "amount",
        "citation_ids",
        "deduction_id",
        "election",
        "estimated",
        "reason_sealed",
        "seq",
        "set_by_id",
        "set_by_kind",
        "tenant_id",
    }
)
INSERT_COLUMNS["estate_deductions"] = frozenset(
    {"created_by", "description", "engagement_id", "schedule", "tenant_id", "work_item_id"}
)
INSERT_COLUMNS["estate_inventory_item_versions"] = frozenset(
    {
        "avd_value",
        "citation_ids",
        "dod_value",
        "item_id",
        "reason_sealed",
        "request_item_id",
        "seq",
        "set_by_id",
        "set_by_kind",
        "status",
        "support_text",
        "tenant_id",
    }
)
INSERT_COLUMNS["estate_inventory_items"] = frozenset(
    {
        "basis_rule",
        "created_by",
        "description",
        "engagement_id",
        "schedule",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["estate_profiles"] = frozenset(
    {
        "client_entity_id",
        "created_by",
        "date_of_death",
        "dsue_amount",
        "dsue_citation_ids",
        "residence_state",
        "tenant_id",
    }
)
UPDATE_COLUMNS["estate_profiles"] = frozenset(
    {"dsue_amount", "dsue_citation_ids", "residence_state", "row_version"}
)
INSERT_COLUMNS["gift_history_item_versions"] = frozenset(
    {
        "evidence_version_id",
        "filed_on",
        "form_709_status",
        "gift_amount",
        "gift_id",
        "reason_sealed",
        "seq",
        "set_by_id",
        "set_by_kind",
        "tenant_id",
    }
)
INSERT_COLUMNS["gift_history_items"] = frozenset(
    {"asset", "client_entity_id", "created_by", "donee_name_sealed", "tenant_id", "year"}
)

# T-06-T10 (0952, DEC-5519): entity depth, every table TRI on a return's work item.
T06T10_TABLES: frozenset[str] = frozenset(
    {
        "basis_schedules",
        "book_tax_items",
        "fixed_asset_dispositions",
        "fixed_asset_versions",
        "fixed_assets",
        "liability_shares",
        "nexus_facts",
        "ptet_elections",
        "ptet_partner_credits",
        "ptet_payments",
        "sourcing_positions",
        "state_apportionments",
        "tax_properties",
    }
)
TABLES: frozenset[str] = _TABLES_BEFORE_S49 | T06T10_TABLES
INSERT_ONLY: frozenset[str] = _INSERT_ONLY_BEFORE_S49 | frozenset(
    {
        "fixed_asset_dispositions",
        "fixed_asset_versions",
        "ptet_payments",
    }
)
INSERT_COLUMNS["tax_properties"] = frozenset(
    {
        "city",
        "code",
        "engagement_id",
        "form8825_property_no",
        "land_value",
        "name",
        "source_ref",
        "state",
        "tenant_id",
        "use",
        "work_item_id",
    }
)
INSERT_COLUMNS["fixed_assets"] = frozenset(
    {
        "accum_bop",
        "accum_eop",
        "acquired_on",
        "asset_no",
        "binding_contract_on",
        "bonus_pct",
        "book_equals_tax",
        "convention",
        "cost",
        "current_year",
        "date_citation_id",
        "description",
        "engagement_id",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "method",
        "placed_in_service_on",
        "property_id",
        "recovery_class",
        "sec179",
        "status",
        "status_reason_code",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["fixed_asset_versions"] = frozenset(
    {
        "asset_id",
        "changed_by",
        "engagement_id",
        "image",
        "proposal_id",
        "tenant_id",
        "version",
        "work_item_id",
    }
)
INSERT_COLUMNS["fixed_asset_dispositions"] = frozenset(
    {
        "asset_id",
        "created_by",
        "disposed_on",
        "engagement_id",
        "gain_loss",
        "proceeds",
        "recapture_1245",
        "tenant_id",
        "unrecaptured_1250",
        "work_item_id",
    }
)
INSERT_COLUMNS["book_tax_items"] = frozenset(
    {
        "account_no",
        "col_a",
        "col_b",
        "col_c",
        "col_d",
        "description",
        "engagement_id",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "kind",
        "line_key",
        "schedule",
        "source_ref",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["basis_schedules"] = frozenset(
    {
        "difference",
        "engagement_id",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "inside_share",
        "outside_basis",
        "partner_id",
        "s743b_placeholder",
        "s752_share",
        "status",
        "tax_capital",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["liability_shares"] = frozenset(
    {
        "engagement_id",
        "liability_kind",
        "method",
        "partner_id",
        "share_bop",
        "share_eop",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["state_apportionments"] = frozenset(
    {
        "denominator",
        "engagement_id",
        "nexus_basis",
        "numerator",
        "property_id",
        "return_form",
        "share",
        "state",
        "status",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["sourcing_positions"] = frozenset(
    {
        "decided_at",
        "decided_by",
        "engagement_id",
        "method",
        "proposal_id",
        "status",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["ptet_elections"] = frozenset(
    {
        "amount",
        "base",
        "election",
        "engagement_id",
        "rate",
        "rounding_rule",
        "state",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["ptet_payments"] = frozenset(
    {
        "amount",
        "engagement_id",
        "evidence_version_id",
        "paid_on",
        "recorded_by",
        "state",
        "tenant_id",
        "with_extension",
        "work_item_id",
    }
)
INSERT_COLUMNS["ptet_partner_credits"] = frozenset(
    {
        "amount",
        "engagement_id",
        "override_reason",
        "partner_id",
        "rounding_rule",
        "state",
        "tenant_id",
        "work_item_id",
    }
)
INSERT_COLUMNS["nexus_facts"] = frozenset(
    {
        "conclusion",
        "engagement_id",
        "evidence_version_id",
        "fact",
        "owner_user_id",
        "state",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["tax_properties"] = frozenset(
    {
        "city",
        "form8825_property_no",
        "land_value",
        "name",
        "source_ref",
        "state",
        "use",
        "version",
    }
)
UPDATE_COLUMNS["fixed_assets"] = frozenset(
    {
        "accum_bop",
        "accum_eop",
        "acquired_on",
        "binding_contract_on",
        "bonus_pct",
        "book_equals_tax",
        "computed_at",
        "convention",
        "cost",
        "current_year",
        "date_citation_id",
        "description",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "method",
        "placed_in_service_on",
        "property_id",
        "recovery_class",
        "sec179",
        "status",
        "status_reason_code",
        "version",
    }
)
UPDATE_COLUMNS["book_tax_items"] = frozenset(
    {
        "col_a",
        "col_b",
        "col_c",
        "col_d",
        "computed_at",
        "description",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "kind",
        "source_ref",
    }
)
UPDATE_COLUMNS["basis_schedules"] = frozenset(
    {
        "computed_at",
        "difference",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "inside_share",
        "outside_basis",
        "s743b_placeholder",
        "s752_share",
        "status",
        "tax_capital",
    }
)
UPDATE_COLUMNS["liability_shares"] = frozenset(
    {
        "method",
        "share_bop",
        "share_eop",
    }
)
UPDATE_COLUMNS["state_apportionments"] = frozenset(
    {
        "denominator",
        "nexus_basis",
        "numerator",
        "return_form",
        "share",
        "status",
    }
)
UPDATE_COLUMNS["sourcing_positions"] = frozenset(
    {
        "decided_at",
        "decided_by",
        "status",
    }
)
UPDATE_COLUMNS["ptet_elections"] = frozenset(
    {
        "amount",
        "base",
        "election",
        "rate",
        "rounding_rule",
        "version",
    }
)
UPDATE_COLUMNS["ptet_partner_credits"] = frozenset(
    {
        "amount",
        "override_reason",
        "rounding_rule",
    }
)
UPDATE_COLUMNS["nexus_facts"] = frozenset(
    {
        "conclusion",
        "evidence_version_id",
        "fact",
        "owner_user_id",
    }
)

# T-08-T06 (0961, DEC-5605).
T08T06_TABLES: frozenset[str] = frozenset(
    {
        "aar_adjustments",
        "aar_elections",
        "amendment_explanation_versions",
        "amendments",
        "planning_opportunity_events",
        "planning_screens",
        "return_supersessions",
        "standards_check_confirmations",
        "standards_check_results",
        "standards_run_items",
        "standards_runs",
        "variance_explanation_acceptances",
        "variance_explanation_versions",
    }
)
TABLES = TABLES | T08T06_TABLES
INSERT_ONLY = INSERT_ONLY | frozenset(
    {
        "aar_elections",
        "amendment_explanation_versions",
        "planning_opportunity_events",
        "planning_screens",
        "return_supersessions",
        "standards_check_confirmations",
        "standards_check_results",
        "variance_explanation_acceptances",
        "variance_explanation_versions",
    }
)
INSERT_COLUMNS["variance_explanation_versions"] = frozenset(
    {
        "author_kind",
        "citations",
        "created_by",
        "engagement_id",
        "line_key",
        "suggestion_id",
        "tenant_id",
        "text",
        "version_no",
        "work_item_id",
    }
)
INSERT_COLUMNS["variance_explanation_acceptances"] = frozenset(
    {
        "accepted_by",
        "tenant_id",
        "threshold_source",
        "values_hash",
        "version_id",
    }
)
INSERT_COLUMNS["standards_runs"] = frozenset(
    {
        "form",
        "standard_version_id",
        "started_by",
        "tenant_id",
    }
)
UPDATE_COLUMNS["standards_runs"] = frozenset(
    {
        "completed_at",
        "status",
    }
)
INSERT_COLUMNS["standards_run_items"] = frozenset(
    {
        "checks_total",
        "engagement_id",
        "run_id",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["standards_run_items"] = frozenset(
    {
        "checks_passed",
        "checks_total",
        "completed_at",
        "status",
    }
)
INSERT_COLUMNS["standards_check_results"] = frozenset(
    {
        "anchor",
        "check_key",
        "created_issue_id",
        "difference",
        "linked_issue_id",
        "outcome",
        "run_item_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["standards_check_confirmations"] = frozenset(
    {
        "confirmed_by",
        "note",
        "outcome",
        "result_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["planning_screens"] = frozenset(
    {
        "agent_run_id",
        "partner_user_id",
        "rules_version",
        "tenant_id",
        "trigger",
        "work_item_id",
    }
)
INSERT_COLUMNS["planning_opportunity_events"] = frozenset(
    {
        "actor_id",
        "event",
        "from_status",
        "note",
        "opportunity_id",
        "reason",
        "tenant_id",
        "to_status",
    }
)
INSERT_COLUMNS["amendments"] = frozenset(
    {
        "baseline_checkpoint_id",
        "created_by",
        "engagement_id",
        "jurisdictions",
        "kind",
        "original_work_item_id",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["amendments"] = frozenset(
    {
        "baseline_checkpoint_id",
        "row_version",
    }
)
INSERT_COLUMNS["amendment_explanation_versions"] = frozenset(
    {
        "amendment_id",
        "author_kind",
        "created_by",
        "edit_dif",
        "suggestion_id",
        "tenant_id",
        "text",
        "version_no",
    }
)
INSERT_COLUMNS["return_supersessions"] = frozenset(
    {
        "ack_id",
        "original_work_item_id",
        "superseded_by_work_item_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["aar_adjustments"] = frozenset(
    {
        "amendment_id",
        "amount",
        "description",
        "position",
        "reviewed_year",
        "tenant_id",
    }
)
UPDATE_COLUMNS["aar_adjustments"] = frozenset(
    {
        "amount",
        "description",
    }
)
INSERT_COLUMNS["aar_elections"] = frozenset(
    {
        "amendment_id",
        "decided_by",
        "decision_id",
        "imputed_underpayment",
        "iu_source",
        "route",
        "tenant_id",
    }
)
# T-08-T06 (0961): T-05's planning_opportunities (0830) widened for rule rows and six statuses.
INSERT_COLUMNS["planning_opportunities"] = INSERT_COLUMNS["planning_opportunities"] | frozenset(
    {
        "category",
        "client_draft_suggestion_id",
        "client_id",
        "consent_basis",
        "consent_id",
        "est_savings",
        "owner_user_id",
        "product_kind",
        "rationale_suggestion_id",
        "rule_key",
        "savings_basis",
        "screen_id",
        "talking_points_suggestion_id",
    }
)
UPDATE_COLUMNS["planning_opportunities"] = UPDATE_COLUMNS["planning_opportunities"] | frozenset(
    {
        "client_draft_suggestion_id",
        "est_savings",
        "owner_user_id",
        "previous_status",
        "project_engagement_id",
        "raised_message_id",
        "rationale_suggestion_id",
        "row_version",
        "savings_basis",
        "status",
        "talking_points_suggestion_id",
    }
)

# T-06-T14 (0966, DEC-5625).
T06T14_TABLES: frozenset[str] = frozenset(
    {
        "aaa_lines",
        "allocation_runs",
        "deferred_tax_items",
        "form_diagnostics",
        "form_page_renders",
        "functional_expense_lines",
        "public_support_tests",
        "rate_recon_items",
        "shareholder_allocations",
        "tax_provisions",
    }
)
TABLES = TABLES | T06T14_TABLES
INSERT_COLUMNS["aaa_lines"] = frozenset(
    {
        "col_aaa",
        "col_e_and_p",
        "col_oaa",
        "col_pti",
        "engagement_id",
        "line_no",
        "source_ref",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["aaa_lines"] = frozenset(
    {
        "col_aaa",
        "col_e_and_p",
        "col_oaa",
        "col_pti",
        "source_ref",
    }
)
INSERT_COLUMNS["shareholder_allocations"] = frozenset(
    {
        "days",
        "distributions",
        "engagement_id",
        "interest",
        "nondeductible",
        "ordinary_income",
        "partner_id",
        "pct",
        "shares",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["shareholder_allocations"] = frozenset(
    {
        "days",
        "distributions",
        "interest",
        "nondeductible",
        "ordinary_income",
        "pct",
        "shares",
    }
)
INSERT_COLUMNS["tax_provisions"] = frozenset(
    {
        "blended_rate",
        "current_tax",
        "deferred_tax",
        "engagement_id",
        "etr",
        "off_amount",
        "permanent_total",
        "pretax_book_income",
        "recon_status",
        "taxable_income",
        "temporary_total",
        "tenant_id",
        "total_provision",
        "work_item_id",
    }
)
UPDATE_COLUMNS["tax_provisions"] = frozenset(
    {
        "blended_rate",
        "current_tax",
        "deferred_tax",
        "etr",
        "off_amount",
        "permanent_total",
        "pretax_book_income",
        "recon_status",
        "taxable_income",
        "temporary_total",
        "total_provision",
    }
)
INSERT_COLUMNS["rate_recon_items"] = frozenset(
    {
        "amount",
        "classification",
        "description",
        "engagement_id",
        "item_key",
        "proposal_id",
        "provision_id",
        "rate_effect",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["rate_recon_items"] = frozenset(
    {
        "amount",
        "classification",
        "description",
        "proposal_id",
        "rate_effect",
    }
)
INSERT_COLUMNS["deferred_tax_items"] = frozenset(
    {
        "amount",
        "engagement_id",
        "kind",
        "label",
        "provision_id",
        "rate",
        "temporary_difference",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["deferred_tax_items"] = frozenset(
    {
        "amount",
        "rate",
        "temporary_difference",
    }
)
INSERT_COLUMNS["functional_expense_lines"] = frozenset(
    {
        "allocation_basis",
        "engagement_id",
        "fundraising",
        "label",
        "management_general",
        "part_ix_line",
        "program",
        "source_memo_evidence_version_id",
        "tenant_id",
        "time_study",
        "total",
        "work_item_id",
    }
)
UPDATE_COLUMNS["functional_expense_lines"] = frozenset(
    {
        "allocation_basis",
        "fundraising",
        "label",
        "management_general",
        "program",
        "source_memo_evidence_version_id",
        "time_study",
        "total",
    }
)
INSERT_COLUMNS["public_support_tests"] = frozenset(
    {
        "engagement_id",
        "pct",
        "public_support",
        "tenant_id",
        "threshold_met",
        "total_support",
        "work_item_id",
        "years",
    }
)
UPDATE_COLUMNS["public_support_tests"] = frozenset(
    {
        "pct",
        "public_support",
        "threshold_met",
        "total_support",
    }
)
INSERT_COLUMNS["allocation_runs"] = frozenset(
    {
        "engagement_id",
        "proposal_id",
        "run_id",
        "status",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["allocation_runs"] = frozenset(
    {
        "proposal_id",
        "status",
    }
)
INSERT_COLUMNS["form_page_renders"] = frozenset(
    {
        "checkpoint_id",
        "engagement_id",
        "generated_document_version_id",
        "page_key",
        "render_hash",
        "status",
        "template_version_id",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["form_page_renders"] = frozenset(
    {
        "generated_document_version_id",
        "render_hash",
        "status",
    }
)
INSERT_COLUMNS["form_diagnostics"] = frozenset(
    {
        "checkpoint_id",
        "engagement_id",
        "engine_import_id",
        "facts",
        "issue_id",
        "rule_key",
        "severity",
        "source",
        "status",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["form_diagnostics"] = frozenset(
    {
        "facts",
        "issue_id",
        "severity",
        "status",
    }
)
