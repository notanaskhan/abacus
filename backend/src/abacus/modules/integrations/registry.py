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
        "integration_mappings",  # 0466 (T-01-T20)
    }
)
INSERT_ONLY: frozenset[str] = frozenset()
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "firm_integrations": frozenset({"tenant_id", "catalog_key", "status", "mode", "created_by"}),
    # Sealed once, never updated; deleting the row removes the only sealed copy.
    "integration_secrets": frozenset({"tenant_id", "firm_integration_id", "sealed", "key_id"}),
    # T-01-T20 (0466): ADM-08's settings and mappings.
    "integration_mappings": frozenset(
        {"tenant_id", "firm_integration_id", "kind", "source_key", "target_value", "direction"}
        | {"updated_by"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "firm_integrations": frozenset({"status", "version"}),
    "integration_mappings": frozenset(
        {"target_value", "direction", "version", "updated_by", "updated_at"}
    ),
}
