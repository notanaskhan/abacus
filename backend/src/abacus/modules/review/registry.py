"""The review module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-308 (TASK-319): sign-offs; SPEC-313 (TASK-325): notes on any reviewable.
TABLES: frozenset[str] = frozenset({"sign_offs", "reviewable_notes", "reviewable_note_events"})
INSERT_ONLY: frozenset[str] = TABLES
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "sign_offs": frozenset(
        {"tenant_id", "engagement_id", "target_type", "target_id", "level", "content_hash"}
        | {"signed_by"}
    ),
}
INSERT_COLUMNS["reviewable_notes"] = frozenset(
    {"tenant_id", "engagement_id", "target_type", "target_id", "anchor", "body", "raised_by"}
)
INSERT_COLUMNS["reviewable_note_events"] = frozenset(
    {"tenant_id", "note_id", "kind", "body", "by_user"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
