"""The review module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-308 (TASK-319): sign-offs; SPEC-313 (TASK-331): notes on any reviewable; P-04-T03
# (migration 0093, ADR-160): field value history and the human-gates projection.
TABLES: frozenset[str] = frozenset(
    {"sign_offs", "reviewable_notes", "reviewable_note_events"}
    | {"field_value_versions", "human_gates"}
    # P-04-T04 (migration 0094): decision cards and decisions, checkpoints, issues.
    | {"decision_cards", "decisions", "checkpoints", "checkpoint_diffs", "checkpoint_decisions"}
    | {"issues", "issue_events", "issue_links"}
    # P-04-T23 (migration 0211): a card's numbered history and its analysis requests.
    | {"decision_card_versions", "decision_analysis_requests"}
    # I-01-T04 (migration 0223): a person's snoozes and reassignments of gates.
    | {"human_gate_snoozes", "human_gate_reassignments"}
)
INSERT_ONLY: frozenset[str] = frozenset(
    {"sign_offs", "reviewable_note_events", "field_value_versions"}
    | {"decisions", "checkpoint_diffs", "checkpoint_decisions", "issue_events", "issue_links"}
    | {"decision_card_versions", "decision_analysis_requests"}
    | {"human_gate_snoozes", "human_gate_reassignments"}  # I-01-T04 (0223)
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
    | {"id"}  # P-04-T21 (migration 0210): the sealed body is bound to its row
)
INSERT_COLUMNS["reviewable_note_events"] = frozenset(
    {"tenant_id", "note_id", "kind", "body", "by_user"}
    | {"id", "body_sealed"}  # P-04-T21 (migration 0210)
)
INSERT_COLUMNS["field_value_versions"] = frozenset(
    {"tenant_id", "engagement_id", "target_type", "target_id", "field_key", "seq", "value"}
    | {"value_kind", "value_source", "cause", "on_behalf_of_user_id", "suggestion_id"}
    | {"checkpoint_id", "citation_ids", "citation_note_sealed", "issue_id"}
)
INSERT_COLUMNS["human_gates"] = frozenset(
    {"tenant_id", "kind", "subject_ref", "engagement_id", "work_item_id", "client_id"}
    | {"assignee_user_id", "role", "due_on", "state", "source_event_id"}
    | {"subkind", "office_id", "blocked", "blocked_reason_code", "sort_hint"}  # I-01-T04 (0223)
)
INSERT_COLUMNS["human_gate_snoozes"] = frozenset(
    {"tenant_id", "gate_id", "user_id", "until", "actor_kind", "actor_id"}
)
INSERT_COLUMNS["human_gate_reassignments"] = frozenset(
    {"tenant_id", "gate_id", "subject_ref", "from_user_id", "to_user_id", "reason_code"}
    | {"actor_kind", "actor_id"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "reviewable_notes": frozenset({"status", "assignee_user_id"}),  # P-04-T03
    "human_gates": frozenset(
        {"state", "assignee_user_id", "due_on", "updated_at"}  # P-04-T03
        | {"office_id", "blocked", "blocked_reason_code", "sort_hint"}  # I-01-T04 (0223)
    ),
}

# P-04-T04 (migration 0094, ADR-160): their insert and update columns.
INSERT_COLUMNS["decision_cards"] = frozenset(
    {"tenant_id", "engagement_id", "work_item_id", "kind", "version_no", "question_key"}
    | {"reserved_role", "reserved_user_id", "options", "context", "factors"}
    | {"recommendation_suggestion_id", "blocking_refs", "supersedes_id", "raised_by_kind"}
    | {"raised_by_id", "run_id"}
)
INSERT_COLUMNS["decisions"] = frozenset(
    {"tenant_id", "card_id", "option_key", "rationale_sealed", "factors", "seen_card_version"}
    | {"decided_by", "mfa_at"}
    | {"id"}  # P-04-T23 (migration 0211): the sealed rationale is bound to its row
)
INSERT_COLUMNS["decision_card_versions"] = frozenset(
    {"tenant_id", "card_id", "version_no", "event", "option_key", "changed", "figures"}
    | {"decision_id", "superseded_by_card_id", "actor_user_id"}
)
INSERT_COLUMNS["decision_analysis_requests"] = frozenset(
    {"id", "tenant_id", "card_id", "text_sealed", "requested_by"}
)
INSERT_COLUMNS["checkpoints"] = frozenset(
    {"tenant_id", "engagement_id", "target_type", "target_id", "seq", "name", "starred"}
    | {"author_kind", "author_ref", "cause", "status", "proposal_id", "restored_from_id"}
    | {"engine_sync_event_id", "content_hash", "run_id"}
)
INSERT_COLUMNS["checkpoint_diffs"] = frozenset(
    {"tenant_id", "checkpoint_id", "field_key", "old", "new", "cause", "citation_ids"}
    | {"delta_facts"}
)
INSERT_COLUMNS["checkpoint_decisions"] = frozenset(
    {"tenant_id", "checkpoint_id", "decision", "reason_code", "note_sealed"}
    | {"proposal_decision_id", "decided_by"}
)
INSERT_COLUMNS["issues"] = frozenset(
    {"id"}  # P-04-T30 (0274): sealed texts bind to the id, minted first
    | {"tenant_id", "engagement_id", "work_item_id", "record_ref", "kind", "priority"}
    | {"title_sealed", "status", "instructions_required", "assignee_user_id", "assignee_agent"}
    | {"client_contact_id", "client_wording_sealed", "internal_note_sealed", "blocks"}
    | {"source_ref"}
)
INSERT_COLUMNS["issue_events"] = frozenset(
    {"tenant_id", "issue_id", "event", "fix_instructions_sealed", "scope"}
)
INSERT_COLUMNS["issue_links"] = frozenset({"tenant_id", "issue_id", "link_kind", "ref"})
UPDATE_COLUMNS["decision_cards"] = frozenset(
    {"status"}
    | {"reserved_user_id"}  # I-01-T04 (0223): the reassign hook, behind its guard trigger
)
UPDATE_COLUMNS["checkpoints"] = frozenset({"name", "starred", "status"})
UPDATE_COLUMNS["issues"] = frozenset(
    {"status", "assignee_user_id", "assignee_agent", "priority", "kind", "title_sealed"}
    | {"version"}
)
