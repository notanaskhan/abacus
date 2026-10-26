"""The integrations module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {
        # 0194 (A-02-T12): global catalogue content; the app reads it through
        # `integration_catalog_rows()` and holds no privilege on the table.
        "integration_catalog",
        "firm_integrations",
        "integration_secrets",
    }
)
INSERT_ONLY: frozenset[str] = frozenset()
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "firm_integrations": frozenset({"tenant_id", "catalog_key", "status", "mode", "created_by"}),
    # Sealed once, never updated; deleting the row removes the only sealed copy.
    "integration_secrets": frozenset({"tenant_id", "firm_integration_id", "sealed", "key_id"}),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "firm_integrations": frozenset({"status", "version"}),
}
