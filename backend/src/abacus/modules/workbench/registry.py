"""The workbench module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# P-10-T04 (0682): sessions, soft-delete only; items, insert-only by trigger.
TABLES: frozenset[str] = frozenset({"workbench_sessions", "session_items"})
INSERT_ONLY: frozenset[str] = frozenset({"session_items"})
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "workbench_sessions": frozenset(
        {"id", "tenant_id", "title", "owner_user_id", "origin", "definition_id", "context_refs"}
        | {"client_scope"}
    ),
    "session_items": frozenset(
        {"id", "tenant_id", "session_id", "seq", "kind", "payload", "run_id", "step_id"}
        | {"actor_kind", "actor_id", "classification"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "workbench_sessions": frozenset(
        {"title", "state", "context_refs", "client_scope", "last_item_at", "item_seq"}
        | {"deleted_at"}
    ),
}
