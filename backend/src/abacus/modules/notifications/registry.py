"""The notifications module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "notifications",  # SPEC-013
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset()
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # Notifications (SPEC-013): identifiers only; one per recipient per event.
    "notifications": frozenset(
        {"id", "tenant_id", "recipient_user_id", "kind", "event_id", "engagement_id"}
        | {"subject_type", "subject_id"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "notifications": frozenset({"read_at"}),  # SPEC-013
}
