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
        # K-01-T05 (0224): a version's programs, steps and their PBC links.
        "programs",
        "program_steps",
        "program_step_pbc_links",
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
        "programs",  # K-01-T05 (0224)
        "program_step_pbc_links",  # K-01-T05 (0224)
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
# K-01-T05 (0224): programs, steps and links, every column set at insert.
INSERT_COLUMNS["programs"] = frozenset(
    {"tenant_id", "version_id", "code", "name", "position", "publisher_program_id"}
)
INSERT_COLUMNS["program_steps"] = frozenset(
    {"id", "tenant_id", "version_id", "program_id", "step_key", "number", "text", "assertions"}
    | {"standard_refs", "level", "mandatory", "lock_note", "guidance", "prepopulates"}
    | {"depends_on_step_keys", "publisher_step_id", "origin", "proposed_by_run_id"}
    | {"parse_confidence", "parse_flag"}
)
INSERT_COLUMNS["program_step_pbc_links"] = frozenset(
    {"tenant_id", "version_id", "step_id", "request_position"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # K-01-T05 (0224): a draft step's content (K-01-T14 edits it); the frozen trigger refuses
    # any change to a published or superseded version's steps.
    "program_steps": frozenset(
        {"number", "text", "assertions", "standard_refs", "level", "guidance", "prepopulates"}
        | {"depends_on_step_keys", "flag_resolution", "flag_resolved_by", "flag_resolved_at"}
        | {"edited_by", "edited_at", "row_version"}
    ),
    "methodology_version_states": frozenset(
        {"status", "effective_from", "effective_to", "approved_by", "approved_at"}
        | {"approved_actor_kind", "approval_basis", "standards_set_id", "quality_management_ref"}
        | {"engagement_types", "default_for_new_engagements", "row_version"}
    ),
}
