"""The review module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-308 (TASK-319): sign-offs; SPEC-313 (TASK-331): notes on any reviewable; P-04-T03
# (migration 0093, ADR-160): field value history and the human-gates projection.
TABLES: frozenset[str] = frozenset(
    {"sign_offs", "reviewable_notes", "reviewable_note_events"}
    | {"field_value_versions", "human_gates"}
)
INSERT_ONLY: frozenset[str] = frozenset(
    {"sign_offs", "reviewable_note_events", "field_value_versions"}
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "sign_offs": frozenset(
        {"tenant_id", "engagement_id", "target_type", "target_id", "level", "content_hash"}
        | {"signed_by"}
        # P-04-T03: what was true at signing.
        | {"kind", "work_item_id", "initials", "engagement_role_at_sign", "function_at_sign"}
        | {"version_no", "statement_version", "adopted_run_id", "independence_checked_at"}
        | {"bulk_request_id"}
    ),
}
INSERT_COLUMNS["reviewable_notes"] = frozenset(
    {"tenant_id", "engagement_id", "target_type", "target_id", "anchor", "body", "raised_by"}
    | {"assignee_user_id", "anchor_ref", "body_sealed"}  # P-04-T03
)
INSERT_COLUMNS["reviewable_note_events"] = frozenset(
    {"tenant_id", "note_id", "kind", "body", "by_user"}
)
INSERT_COLUMNS["field_value_versions"] = frozenset(
    {"tenant_id", "engagement_id", "target_type", "target_id", "field_key", "seq", "value"}
    | {"value_kind", "value_source", "cause", "on_behalf_of_user_id", "suggestion_id"}
    | {"checkpoint_id", "citation_ids", "citation_note_sealed", "issue_id"}
)
INSERT_COLUMNS["human_gates"] = frozenset(
    {"tenant_id", "kind", "subject_ref", "engagement_id", "work_item_id", "client_id"}
    | {"assignee_user_id", "role", "due_on", "state", "source_event_id"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "reviewable_notes": frozenset({"status", "assignee_user_id"}),  # P-04-T03
    "human_gates": frozenset({"state", "assignee_user_id", "due_on", "updated_at"}),  # P-04-T03
}
