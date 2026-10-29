"""The practice module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# I-01-T12 (migration 0320): HOME-01's client activity projection. Inserted once per event and
# pruned after 90 days (the app role may delete), never updated.
TABLES: frozenset[str] = frozenset({"home_activity_items"})
INSERT_ONLY: frozenset[str] = frozenset()
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "home_activity_items": frozenset(
        {"tenant_id", "source_event_id", "event_type", "occurred_at", "client_id"}
        | {"engagement_id", "work_item_id", "office_id", "actor_kind", "actor_ref"}
        | {"subject_ref", "facts"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
