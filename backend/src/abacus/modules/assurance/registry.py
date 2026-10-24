"""The assurance module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-314 (TASK-332): completion, release and archive, all insert-only and human-only.
# A-01-T05 (0134): the record-mode phase events, insert-only and human-only when recorded.
TABLES: frozenset[str] = frozenset(
    {"eqr_concurrences", "completion_records", "releases", "archives", "assurance_phase_events"}
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
    "assurance_phase_events": frozenset(
        {"tenant_id", "engagement_id", "work_item_id", "from_phase", "to_phase", "mode"}
        | {"reason_sealed", "gate_ref", "actor_kind", "actor_user_id", "mfa_at"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
