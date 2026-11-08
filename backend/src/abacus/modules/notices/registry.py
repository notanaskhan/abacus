"""The notices module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. N-04-T03 (0650, DEC-2052):
notices v1, its intakes, insert-only records and the response.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {"notices"}  # F-03-T22 (0089)
    # N-04-T03 (0650): the v1 tables.
    | {"notice_intakes", "notice_responses"}
    | {
        "notice_status_events",
        "notice_field_values",
        "notice_proposed_items",
        "notice_return_snapshots",
        "notice_analyses",
    }
    | {"notice_notes", "notice_response_versions", "notice_sent_records", "notice_agency_replies"}
)
# 0650: `notices` takes updates of its v1 columns now, so it is no longer insert-only.
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "notice_status_events",
        "notice_field_values",
        "notice_proposed_items",
        "notice_return_snapshots",
        "notice_analyses",
        "notice_notes",
        "notice_response_versions",
        "notice_sent_records",
        "notice_agency_replies",
    }
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "notices": frozenset(
        {
            "agency",
            "agency_name",
            "amount_interest",
            "amount_penalty",
            "amount_tax",
            "amount_total",
            "assignee_user_id",
            "authorization_id",
            "authorization_kind",
            "client_entity_id",
            "client_id",
            "client_visible",
            "closed_on",
            "decided_at",
            "decision_id",
            "engagement_id",
            "escalated_reason",
            "follow_up_on",
            "form",
            "interest_to",
            "jurisdiction",
            "notice_code",
            "notice_date",
            "notice_type_key",
            "partner_owned",
            "position",
            "received_on",
            "related_return_id",
            "respond_by",
            "respond_by_source",
            "source_evidence_version_id",
            "source_intake_id",
            "status",
            "tax_year",
            "taxpayer_tin_last4",
            "tenant_id",
            "title",
            "work_item_id",
        }
    ),
    "notice_status_events": frozenset(
        {
            "actor_kind",
            "actor_user_id",
            "from_status",
            "reason_code",
            "tenant_id",
            "to_status",
            "work_item_id",
        }
    ),
    "notice_intakes": frozenset(
        {
            "assignee_user_id",
            "authorization_facts",
            "client_id",
            "created_by",
            "evidence_version_id",
            "extraction_mode",
            "inbox_item_id",
            "match",
            "notify_user_ids",
            "source",
            "status",
            "tenant_id",
        }
    ),
    "notice_field_values": frozenset(
        {
            "agent_run_id",
            "citation_id",
            "confidence",
            "confirmed_by",
            "extracted_field_id",
            "field_key",
            "last4",
            "low_confidence",
            "origin",
            "owner_id",
            "owner_type",
            "recorded_actor_kind",
            "recorded_by",
            "supersedes_id",
            "tenant_id",
            "value_sealed",
            "value_text",
            "value_type",
        }
    ),
    "notice_proposed_items": frozenset(
        {
            "amount_irs",
            "amount_shown",
            "citation_id",
            "info_form",
            "kind",
            "label",
            "line_key",
            "origin",
            "payer_name",
            "recorded_actor_kind",
            "recorded_by",
            "supersedes_id",
            "tenant_id",
            "work_item_id",
        }
    ),
    "notice_return_snapshots": frozenset(
        {
            "engine_summary_id",
            "filed_on",
            "filing_status",
            "inputs_hash",
            "lines",
            "recorded_actor_kind",
            "recorded_by",
            "source",
            "tax_return_id",
            "tenant_id",
            "work_item_id",
        }
    ),
    "notice_analyses": frozenset(
        {
            "agent_run_id",
            "agent_stage",
            "analysis_kind",
            "checks",
            "engine_name",
            "engine_version",
            "information_returns",
            "inputs_hash",
            "recommended_position",
            "rows",
            "sources",
            "status",
            "tenant_id",
            "version",
            "work_item_id",
        }
    ),
    "notice_notes": frozenset(
        {
            "author_id",
            "body_sealed",
            "decision_card_id",
            "tenant_id",
            "work_item_id",
        }
    ),
    "notice_responses": frozenset(
        {
            "channel",
            "enclosures",
            "follow_up_days",
            "owner_user_id",
            "payment",
            "position_source",
            "signer_contact_ids",
            "template_key",
            "template_version_id",
            "tenant_id",
            "work_item_id",
        }
    ),
    "notice_response_versions": frozenset(
        {
            "based_on_version_id",
            "blocks",
            "content_hash",
            "created_actor_kind",
            "created_by",
            "edit_diff",
            "response_id",
            "tenant_id",
            "version_no",
        }
    ),
    "notice_sent_records": frozenset(
        {
            "channel",
            "confirmation_last4",
            "confirmation_sealed",
            "follow_up_on",
            "recorded_actor_kind",
            "recorded_by",
            "response_id",
            "sent_on",
            "supersedes_id",
            "tenant_id",
            "work_item_id",
        }
    ),
    "notice_agency_replies": frozenset(
        {
            "closed_on",
            "evidence_version_id",
            "note_sealed",
            "outcome",
            "recorded_actor_kind",
            "recorded_by",
            "tenant_id",
            "work_item_id",
        }
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "notices": frozenset(
        {
            "agency",
            "agency_name",
            "amount_interest",
            "amount_penalty",
            "amount_tax",
            "amount_total",
            "assignee_user_id",
            "authorization_id",
            "authorization_kind",
            "client_entity_id",
            "client_id",
            "client_visible",
            "closed_on",
            "decided_at",
            "decision_id",
            "escalated_reason",
            "follow_up_on",
            "form",
            "interest_to",
            "jurisdiction",
            "notice_date",
            "notice_type_key",
            "partner_owned",
            "position",
            "related_return_id",
            "respond_by",
            "respond_by_source",
            "row_version",
            "source_evidence_version_id",
            "source_intake_id",
            "status",
            "status_changed_at",
            "tax_year",
            "taxpayer_tin_last4",
            "title",
        }
    ),
    "notice_intakes": frozenset(
        {
            "assignee_user_id",
            "authorization_facts",
            "client_id",
            "create_anyway_reason_code",
            "created_work_item_id",
            "discarded_reason_code",
            "duplicate_of_work_item_id",
            "extraction_mode",
            "match",
            "notify_user_ids",
            "row_version",
            "status",
        }
    ),
    "notice_responses": frozenset(
        {
            "binder_id",
            "channel",
            "current_version_id",
            "enclosures",
            "envelope_id",
            "follow_up_days",
            "generated_document_id",
            "owner_user_id",
            "payment",
            "position_source",
            "row_version",
            "signer_contact_ids",
            "template_key",
            "template_version_id",
        }
    ),
}
