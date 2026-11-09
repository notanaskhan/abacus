"""The collaboration module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. P-05-T04 (migration 0760;
SPEC-650; ADR-236 proposed): comments v2 and to-dos. The SPEC-032 `comments` tables stay with
`requests` until CL-1.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {
        "comment_threads",
        "comment_thread_events",
        "thread_comments",
        "thread_comment_mentions",
        "thread_comment_redactions",
        "comment_thread_reads",
        "todos",
        "todo_checklist_items",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004; ADR-236 decision 4).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "comment_thread_events",
        "thread_comments",
        "thread_comment_mentions",
        "thread_comment_redactions",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "comment_threads": frozenset(
        {"id", "tenant_id", "engagement_id", "work_item_id", "client_id", "anchor_kind"}
        | {"anchor_id", "anchor_locator", "anchor_locator_key", "opened_on_version_no"}
        | {"pinned_version_no", "status", "visibility", "shared_scope_kind", "shared_scope_id"}
        | {"created_by", "last_comment_at"}
    ),
    "comment_thread_events": frozenset(
        {"id", "tenant_id", "engagement_id", "thread_id", "kind", "actor_user_id", "actor_kind"}
        | {"ref_type", "ref_id"}
    ),
    "thread_comments": frozenset(
        {"id", "tenant_id", "engagement_id", "thread_id", "author_user_id", "author_side"}
        | {"body_sealed", "body_fingerprint", "corrects_comment_id", "citation_ids"}
    ),
    "thread_comment_mentions": frozenset({"tenant_id", "comment_id", "user_id", "via_team"}),
    "thread_comment_redactions": frozenset({"tenant_id", "comment_id", "redacted_by", "reason"}),
    "comment_thread_reads": frozenset(
        {"tenant_id", "user_id", "thread_id", "last_read_at", "muted_at"}
    ),
    "todos": frozenset(
        {"id", "tenant_id", "scope_kind", "engagement_id", "work_item_id", "client_id", "title"}
        | {"status", "assignee_user_id", "due_on", "anchor_kind", "anchor_id", "anchor_locator"}
        | {"row_text_sealed", "row_text_fingerprint", "source_thread_id", "created_by"}
    ),
    "todo_checklist_items": frozenset({"id", "tenant_id", "todo_id", "position", "text"}),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # The status projection beside its events, visibility and the share scope (ADR-236 5, 9).
    "comment_threads": frozenset(
        {"status", "visibility", "shared_scope_kind", "shared_scope_id", "last_comment_at"}
        | {"updated_at"}
    ),
    "comment_thread_reads": frozenset({"last_read_at", "muted_at"}),
    "todos": frozenset(
        {"title", "status", "assignee_user_id", "due_on", "anchor_kind", "anchor_id"}
        | {"anchor_locator", "work_item_id", "done_by", "done_at", "assignee_seen_at"}
        | {"deleted_at", "deleted_by", "version", "updated_at"}
    ),
    "todo_checklist_items": frozenset({"position", "text", "done", "done_by", "done_at"}),
}
