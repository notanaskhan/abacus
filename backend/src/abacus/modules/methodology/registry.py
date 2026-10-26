"""The methodology module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. K-01-T02 (migration 0180)
re-owned the five SPEC-008 tables from engagements and added the version lifecycle.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {
        "methodology_templates",
        "methodology_versions",
        "methodology_areas",
        "methodology_request_items",
        "methodology_account_rules",
        "methodology_version_states",  # mutable under guarded transitions
        "methodology_version_events",
        "standards_sets",  # global; no app privilege (reference data, K-02's publish path)
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "methodology_templates",
        "methodology_versions",
        "methodology_areas",
        "methodology_request_items",
        "methodology_account_rules",
        "methodology_version_events",
    }
)
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # Methodology templates (SPEC-008): insert-only, immutable versions.
    "methodology_templates": frozenset(
        {"id", "tenant_id", "name", "created_by", "engagement_types"}  # SPEC-024: types served
        | {"family"}  # K-01-T02 (0180)
    ),
    "methodology_versions": frozenset(
        {"id", "tenant_id", "template_id", "version", "source_fingerprint", "imported_by"}
        | {"label", "drafted_from_version_id", "origin"}  # K-01-T02 (0180)
    ),
    "methodology_areas": frozenset({"tenant_id", "version_id", "code", "name", "position"}),
    "methodology_request_items": frozenset(
        {"tenant_id", "version_id", "area_code", "description", "retrievability_tier"}
        | {"position"}
        | {"why", "good_looks_like", "blocks_fieldwork", "effort"}  # SPEC-031 (TASK-060)
        | {"guidance_source", "guidance_approved_by"}  # SPEC-035 Q3 (TASK-074)
    ),
    "methodology_account_rules": frozenset(
        {"tenant_id", "version_id", "area_code", "account_from", "account_to", "position"}
    ),
    "methodology_version_states": frozenset(
        {"tenant_id", "version_id", "template_id", "status", "effective_from", "effective_to"}
        | {"approved_by", "approved_at", "approved_actor_kind", "approval_basis"}
        | {"standards_set_id", "quality_management_ref", "engagement_types"}
        | {"default_for_new_engagements", "row_version"}
    ),
    "methodology_version_events": frozenset(
        {"tenant_id", "version_id", "kind", "actor_user_id", "on_behalf_of_user_id", "facts"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "methodology_version_states": frozenset(
        {"status", "effective_from", "effective_to", "approved_by", "approved_at"}
        | {"approved_actor_kind", "approval_basis", "standards_set_id", "quality_management_ref"}
        | {"engagement_types", "default_for_new_engagements", "row_version", "updated_at"}
    ),
}
