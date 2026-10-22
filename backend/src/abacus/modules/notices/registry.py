"""The notices module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. Empty until its first table.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset({"notices"})  # F-03-T22 (0089)
INSERT_ONLY: frozenset[str] = frozenset({"notices"})
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "notices": frozenset(
        {"tenant_id", "work_item_id", "engagement_id", "notice_code", "received_on"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
