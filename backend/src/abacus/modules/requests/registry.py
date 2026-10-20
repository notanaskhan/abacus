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
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "request_lists": frozenset(
        {"id", "tenant_id", "engagement_id"}
        | {"work_item_id", "name", "kind", "part", "status", "prior_year_source_ref"}  # F-03-T14
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
    ),
    "client_item_responses": frozenset(
        {"tenant_id", "engagement_id", "request_item_id", "kind", "reason", "note", "by_user"}
    ),  # SPEC-042 (TASK-106)
    "client_list_done": frozenset({"tenant_id", "engagement_id", "by_user"}),  # SPEC-042
    "fulfilments": frozenset(
        {"id", "tenant_id", "request_item_id", "evidence_version_id", "created_by_kind"}
        | {"created_by_id", "engagement_id"}
    ),
    # Comments (SPEC-032; TASK-062): the text sealed; mentions, redactions, last reads.
    "comments": frozenset(
        {"id", "tenant_id", "engagement_id", "request_item_id", "evidence_version_id"}
        | {"author_user_id", "author_side", "visibility", "body_sealed", "body_fingerprint"}
        | {"corrects_comment_id"}
    ),
    "comment_mentions": frozenset({"tenant_id", "comment_id", "user_id"}),
    "comment_redactions": frozenset({"tenant_id", "comment_id", "redacted_by", "reason"}),
    "comment_reads": frozenset(
        {"tenant_id", "user_id", "request_item_id", "evidence_version_id", "last_read_at"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "request_lists": frozenset(
        {"default_due_on"}  # SPEC-027 (TASK-051)
        | {"status", "published_at", "published_by", "marked_done_at", "marked_done_by"}  # T14
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
    ),
    "comment_reads": frozenset({"last_read_at"}),  # SPEC-032 (TASK-062)
}
