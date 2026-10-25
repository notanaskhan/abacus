"""The requests module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "request_lists",
        "request_categories",  # F-03-T14 (0070)
        "request_items",
        "client_item_responses",  # SPEC-042 (TASK-106)
        "client_list_done",
        "fulfilments",
        "comments",
        "comment_mentions",
        "comment_redactions",
        "comment_reads",
        # P-06-T05 (0100): the binder engine.
        "binder_recipients",
        "request_delegations",
        "request_upload_intents",
        "binder_activity",
        "fulfilment_withdrawals",  # P-06-T19 (0145; ADR-162)
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "request_categories",  # F-03-T14 (0070)
        "client_item_responses",  # SPEC-042 (TASK-106): as the client said
        "client_list_done",  # SPEC-042 (TASK-106): as the client said
        "fulfilments",
        "comments",  # SPEC-032 (TASK-062): ADR-109
        "comment_mentions",  # SPEC-032 (TASK-062): ADR-109
        "comment_redactions",  # SPEC-032 (TASK-062): ADR-109
        "binder_recipients",  # P-06-T05 (0100): a removal is a new row
        "fulfilment_withdrawals",  # P-06-T19 (0145): a withdrawn version's voided links
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "request_lists": frozenset(
        {"id", "tenant_id", "engagement_id"}
        | {"work_item_id", "name", "kind", "part", "status", "prior_year_source_ref"}  # F-03-T14
        | {"created_from", "template_ref"}  # P-06-T05 (0100)
    ),
    "request_categories": frozenset(  # F-03-T14 (0070)
        {"tenant_id", "request_list_id", "name", "position"}
    ),
    "request_items": frozenset(
        {"id", "tenant_id", "engagement_id", "request_list_id", "description", "audit_area"}
        | {"created_by", "retrievability_tier"}
        | {"dataset", "tier_source", "tier_rule"}  # SPEC-022
        | {"document_kind", "document_kind_source"}  # SPEC-029 (TASK-055)
        | {"why", "good_looks_like", "blocks_fieldwork", "effort", "guidance_source"}  # SPEC-031
        | {"guidance_approved_by"}  # SPEC-035 (TASK-074): from a drafted template, or rolled
        # P-06-T05 (0100): the binder engine's request fields and drafted-wording provenance.
        | {"title", "category_id", "firm_owner_user_id", "period_start", "period_end", "wave"}
        | {"kind", "source_tag", "supports_ref", "linked_ref", "drafted_by_run_id"}
        | {"drafted_wording_source", "drafted_wording_fingerprint"}
    ),
    "binder_recipients": frozenset(  # P-06-T05 (0100)
        {"tenant_id", "binder_id", "contact_id", "added_by", "removed_at"}
    ),
    "request_delegations": frozenset(
        {"tenant_id", "request_item_id", "contact_id", "grant_id", "granted_by"}
    ),
    "request_upload_intents": frozenset(
        {"tenant_id", "request_item_id", "user_id", "files_expected"}
    ),
    "binder_activity": frozenset(
        {"tenant_id", "binder_id", "work_item_id", "status", "open_count"}
        | {"last_client_activity_at"}
    ),
    "client_item_responses": frozenset(
        {"tenant_id", "engagement_id", "request_item_id", "kind", "reason", "note", "by_user"}
    ),  # SPEC-042 (TASK-106)
    "client_list_done": frozenset({"tenant_id", "engagement_id", "by_user"}),  # SPEC-042
    "fulfilments": frozenset(
        {"id", "tenant_id", "request_item_id", "evidence_version_id", "created_by_kind"}
        | {"created_by_id", "engagement_id"}
    ),
    # P-06-T19 (0145): the guard binds the withdrawing person.
    "fulfilment_withdrawals": frozenset(
        {"tenant_id", "fulfilment_id", "engagement_id", "request_item_id"}
        | {"evidence_version_id", "withdrawn_by_user_id"}
    ),
    # Comments (SPEC-032; TASK-062): the text sealed; mentions, redactions, last reads.
    "comments": frozenset(
        {"id", "tenant_id", "engagement_id", "request_item_id", "evidence_version_id"}
        | {"author_user_id", "author_side", "visibility", "body_sealed", "body_fingerprint"}
        | {"corrects_comment_id"}
        | {"origin"}  # R-01-T08 (0157): `ignore_note` for a client's note on an Ignore
    ),
    "comment_mentions": frozenset({"tenant_id", "comment_id", "user_id"}),
    "comment_redactions": frozenset({"tenant_id", "comment_id", "redacted_by", "reason"}),
    "comment_reads": frozenset(
        {"tenant_id", "user_id", "request_item_id", "evidence_version_id", "last_read_at"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "fulfilments": frozenset({"voided_at", "voided_by", "void_reason"}),  # R-01 Story 2.2 (0159)
    "request_lists": frozenset(
        {"default_due_on"}  # SPEC-027 (TASK-051)
        | {"status", "published_at", "published_by", "marked_done_at", "marked_done_by"}  # T14
        | {"unpublished_at", "unpublished_by", "unpublish_reason_sealed"}  # P-06-T05 (0100)
        | {"follow_up_override", "closed_at", "closed_reason"}
    ),
    "request_items": frozenset(
        {"status", "client_visible", "client_assignee_user_id"}
        | {"retrievability_tier", "dataset", "tier_source", "tier_rule"}  # SPEC-022
        | {"due_on"}  # SPEC-027 (TASK-051)
        | {"document_kind", "document_kind_source"}  # SPEC-029 (TASK-055)
        | {"why", "good_looks_like", "still_needed", "blocks_fieldwork", "effort"}  # SPEC-031
        | {"guidance_source"}
        | {"guidance_approved_by"}  # SPEC-035 (TASK-073)
        | {"sent_at", "na_reason", "na_note", "na_by", "na_at", "client_ignored_at"}  # F-03-T15
        | {"incorporation_state", "incorporated_by", "incorporated_at"}
        # P-06-T05 (0100)
        | {"title", "category_id", "firm_owner_user_id", "period_start", "period_end", "wave"}
        | {"supports_ref", "linked_ref", "sent_by", "deleted_at", "deleted_by"}
        | {"description"}  # P-06-T10 (0113): the client wording, edited before it closes
    ),
    "request_delegations": frozenset({"revoked_at"}),  # P-06-T05 (0100)
    "binder_activity": frozenset(  # P-06-T05 (0100): a projection
        {"status", "open_count", "last_client_activity_at", "updated_at"}
    ),
    "comment_reads": frozenset({"last_read_at"}),  # SPEC-032 (TASK-062)
}
