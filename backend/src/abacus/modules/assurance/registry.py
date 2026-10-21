"""The assurance module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-314 (TASK-332): completion, release and archive, all insert-only and human-only.
TABLES: frozenset[str] = frozenset(
    {"eqr_concurrences", "completion_records", "releases", "archives"}
)
INSERT_ONLY: frozenset[str] = TABLES
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "eqr_concurrences": frozenset(
        {"tenant_id", "engagement_id", "digest_hash", "not_involved", "concurred_by", "actor_kind"}
    ),
    "completion_records": frozenset(
        {"tenant_id", "engagement_id", "kind", "choice", "emphasis", "document_date"}
        | {"evidence_version_id", "report_record_id", "rationale", "recorded_by", "actor_kind"}
    ),
    "releases": frozenset(
        {"tenant_id", "engagement_id", "report_record_id", "report_date", "documentation_due"}
        | {"gates", "released_by", "actor_kind"}
    ),
    "archives": frozenset(
        {"tenant_id", "engagement_id", "seal", "leaf_count", "manifest", "locked_by", "actor_kind"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
