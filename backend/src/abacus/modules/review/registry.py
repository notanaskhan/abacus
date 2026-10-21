"""The review module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset({"sign_offs"})  # SPEC-308 (TASK-319): the P-04 first table
INSERT_ONLY: frozenset[str] = frozenset({"sign_offs"})
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "sign_offs": frozenset(
        {"tenant_id", "engagement_id", "target_type", "target_id", "level", "content_hash"}
        | {"signed_by"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
