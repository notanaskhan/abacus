"""The tax module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. Empty until its first table.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset({"tax_returns"})  # F-03-T22 (0089)
INSERT_ONLY: frozenset[str] = frozenset({"tax_returns"})
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "tax_returns": frozenset(
        {"tenant_id", "work_item_id", "engagement_id", "client_entity_id", "form", "tax_year"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
