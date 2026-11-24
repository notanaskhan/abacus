"""The methodology module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. K-01-T02 (migration 0180)
re-owned the five SPEC-008 tables from engagements and added the version lifecycle.
"""

from __future__ import annotations

_TABLES_PRE_S53: frozenset[str] = frozenset(
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
        # K-02-T04 (0401): firm standards and threshold policies, and their versions.
        "firm_standards",
        "firm_standard_versions",
        "threshold_policies",
        "threshold_policy_versions",
        # P-11-T06 (0460): report templates as firm content (C11 §2).
        "report_templates",
        "report_template_versions",
        "report_template_publications",
        "report_template_consent_terms",  # T-01-T17 (0461)
        # K-01-T18 (0580): import review.
        "methodology_imports",  # status, version and progress move under guarded updates
        "methodology_source_files",
        "methodology_source_pages",
        "program_step_sources",
        "disclosure_checklist_templates",
        "disclosure_checklist_template_versions",
        "statement_note_templates",  # A-06-T25 (0674, DEC-2389)
        "statement_note_template_versions",
        "assurance_checklist_templates",  # A-07-T22 (0741, DEC-2806)
        "assurance_checklist_template_versions",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
_INSERT_ONLY_PRE_S53: frozenset[str] = frozenset(
    {
        "methodology_templates",
        "methodology_versions",
        "methodology_areas",
        "methodology_request_items",
        "methodology_account_rules",
        "methodology_version_events",
        "programs",  # K-01-T05 (0224)
        "program_step_pbc_links",  # K-01-T05 (0224)
        "methodology_source_files",  # K-01-T18 (0580)
        "methodology_source_pages",  # K-01-T18 (0580)
        "program_step_sources",  # K-01-T18 (0580)
        "report_templates",  # P-11-T06 (0460): identity never moves
        "report_template_versions",  # P-11-T06 (0460)
        "report_template_publications",  # P-11-T06 (0460)
        "report_template_consent_terms",  # T-01-T17 (0461)
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
    | {"template_refs"}  # A-04-T07 (0614): the templates a step points at
)
INSERT_COLUMNS["program_step_pbc_links"] = frozenset(
    {"tenant_id", "version_id", "step_id", "request_position"}
)
# K-02-T04 (0401): a standard and its drafts; the guard trigger numbers versions and refuses
# any change once a version is published or discarded.
_STANDARD_INSERT = frozenset(
    {"id", "tenant_id", "kind", "key", "name", "owner_id", "applies_to", "created_by"}
)
_VERSION_INSERT = frozenset(
    {"id", "tenant_id", "parent_id", "version", "payload", "payload_schema_version"}
    | {"payload_hash", "change_summary", "drafted_from_version_id", "drafted_by"}
)
for _parent, _versions in (
    ("firm_standards", "firm_standard_versions"),
    ("threshold_policies", "threshold_policy_versions"),
):
    INSERT_COLUMNS[_parent] = _STANDARD_INSERT
    INSERT_COLUMNS[_versions] = _VERSION_INSERT
# P-11-T06 (0460): templates, their versions and publications, every column set at insert.
INSERT_COLUMNS["report_templates"] = frozenset(
    {"id", "tenant_id", "family", "name", "description", "created_by_user_id"}
)
INSERT_COLUMNS["report_template_versions"] = frozenset(
    {"id", "tenant_id", "template_id", "version_no", "layout_key", "body", "clauses"}
    | {"variables", "sample_data", "source", "content_sha256", "imported_by_user_id"}
)
INSERT_COLUMNS["report_template_publications"] = frozenset(
    {"id", "tenant_id", "version_id", "action", "by_user_id", "mfa_at"}
)
# T-01-T17 (0461): a consent template version's terms, frozen with it.
INSERT_COLUMNS["report_template_consent_terms"] = frozenset(
    {"id", "tenant_id", "template_version_id", "purpose", "statement_version"}
    | {"counsel_attested_by_user_id", "expiry_months"}
)
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # K-01-T05 (0224): a draft step's content (K-01-T14 edits it); the frozen trigger refuses
    # any change to a published or superseded version's steps.
    "program_steps": frozenset(
        {"number", "text", "assertions", "standard_refs", "level", "guidance", "prepopulates"}
        | {"depends_on_step_keys", "flag_resolution", "flag_resolved_by", "flag_resolved_at"}
        | {"edited_by", "edited_at", "row_version"}
        | {"template_refs"}  # A-04-T07 (0614)
        # K-01-T14 (0464): mandatory locks, set by a person only (the lock trigger).
        | {"mandatory", "lock_note"}
    ),
    "methodology_version_states": frozenset(
        {"status", "effective_from", "effective_to", "approved_by", "approved_at"}
        | {"approved_actor_kind", "approval_basis", "standards_set_id", "quality_management_ref"}
        | {"engagement_types", "default_for_new_engagements", "row_version"}
    ),
    # K-02-T04 (0401): an owner change and a draft's edit, publish or discard.
    "firm_standards": frozenset({"name", "owner_id", "applies_to", "row_version"}),
    "threshold_policies": frozenset({"name", "owner_id", "applies_to", "row_version"}),
    "firm_standard_versions": frozenset(
        {"status", "effective_from", "payload", "payload_hash", "change_summary"}
        | {"published_by", "published_actor_kind", "published_at", "row_version"}
    ),
    "threshold_policy_versions": frozenset(
        {"status", "effective_from", "payload", "payload_hash", "change_summary"}
        | {"published_by", "published_actor_kind", "published_at", "row_version"}
    ),
}

# A-06-T19 (0660, DEC-2209): statements v1 (DEC-80) and the disclosure-checklist templates.
INSERT_COLUMNS["disclosure_checklist_templates"] = frozenset(
    {"created_by", "framework_key", "name", "tenant_id"}
)
INSERT_COLUMNS["disclosure_checklist_template_versions"] = frozenset(
    {"imported_by", "items", "source_file_sha256", "template_id", "tenant_id", "version"}
)
UPDATE_COLUMNS["disclosure_checklist_template_versions"] = frozenset(
    {"published_at", "published_by", "status"}
)
# A-07-T22 (0741, DEC-2806): the completion, EQR and archive checklist templates.
INSERT_COLUMNS["assurance_checklist_templates"] = frozenset(
    {"created_by", "engagement_type", "kind", "name", "tenant_id"}
)
INSERT_COLUMNS["assurance_checklist_template_versions"] = frozenset(
    {"imported_by", "items", "source_file_sha256", "template_id", "tenant_id", "version"}
)
UPDATE_COLUMNS["assurance_checklist_template_versions"] = frozenset(
    {"published_at", "published_by", "status"}
)
# A-06-T25 (0674, DEC-2389): the statements' note templates
INSERT_COLUMNS["statement_note_templates"] = frozenset(
    {"created_by", "framework_key", "name", "tenant_id"}
)
INSERT_COLUMNS["statement_note_template_versions"] = frozenset(
    {"imported_by", "notes", "source_file_sha256", "template_id", "tenant_id", "version"}
)
UPDATE_COLUMNS["statement_note_template_versions"] = frozenset(
    {"published_at", "published_by", "status"}
)

# K-03-T11 (1010, TASK-8901; SPEC-720 §4): templates v2 core. Components move only while their
# version is a draft (template_component_guard); a published version moves only its deprecate and
# retire fields (template_version_guard).
_TABLES_S53_1: frozenset[str] = frozenset(
    {
        "agent_skill_versions",
        "agent_skills",
        "engagement_templates",
        "scoping_rules",
        "template_agent_column_defs",
        "template_changes",
        "template_form_fields",
        "template_forms",
        "template_report_template_refs",
        "template_requests",
        "template_sheet_columns",
        "template_sheet_definitions",
        "template_sheet_views",
        "template_skill_pins",
        "template_trigger_defaults",
        "template_versions",
    }
)
_INSERT_ONLY_S53_1: frozenset[str] = frozenset(
    {"agent_skills", "agent_skill_versions", "template_changes"}
)
INSERT_COLUMNS["agent_skill_versions"] = frozenset(
    {
        "body_md",
        "body_sha256",
        "created_by",
        "eval_passed",
        "eval_total",
        "id",
        "linked_step_keys",
        "pass_bar",
        "published_at",
        "published_by",
        "skill_id",
        "source",
        "status",
        "tenant_id",
        "version",
    }
)
INSERT_COLUMNS["agent_skills"] = frozenset(
    {"created_by", "id", "name", "skill_group", "skill_key", "tenant_id"}
)
INSERT_COLUMNS["engagement_templates"] = frozenset(
    {
        "engagement_types",
        "family",
        "id",
        "methodology_template_id",
        "name",
        "owner_user_id",
        "service_line",
        "tenant_id",
    }
)
INSERT_COLUMNS["scoping_rules"] = frozenset(
    {
        "conditions",
        "effect",
        "group_op",
        "id",
        "label",
        "position",
        "target_kind",
        "target_ref",
        "template_version_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["template_agent_column_defs"] = frozenset(
    {
        "default_scope",
        "id",
        "instruction_doc",
        "options",
        "output_type",
        "runs_as_capability",
        "sheet_column_id",
        "skill_key",
        "template_version_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["template_changes"] = frozenset(
    {
        "change_key",
        "component",
        "from_version_id",
        "item_ref",
        "kind",
        "summary",
        "tenant_id",
        "to_version_id",
    }
)
INSERT_COLUMNS["template_form_fields"] = frozenset(
    {
        "classification",
        "config",
        "field_key",
        "form_id",
        "id",
        "label",
        "position",
        "required",
        "template_version_id",
        "tenant_id",
        "type",
    }
)
INSERT_COLUMNS["template_forms"] = frozenset(
    {"form_key", "id", "position", "template_version_id", "tenant_id", "title"}
)
INSERT_COLUMNS["template_report_template_refs"] = frozenset(
    {
        "id",
        "report_template_id",
        "report_template_version_id",
        "role",
        "template_version_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["template_requests"] = frozenset(
    {
        "group_key",
        "id",
        "methodology_request_item_id",
        "position",
        "request_key",
        "shown_by_rule_id",
        "step_key",
        "template_version_id",
        "tenant_id",
        "title",
    }
)
INSERT_COLUMNS["template_sheet_columns"] = frozenset(
    {
        "classification",
        "classification_reason",
        "client_visible",
        "column_key",
        "config",
        "default_value",
        "description",
        "id",
        "name",
        "position",
        "required",
        "sheet_definition_id",
        "source_binding",
        "template_version_id",
        "tenant_id",
        "type",
        "validation",
    }
)
INSERT_COLUMNS["template_sheet_definitions"] = frozenset(
    {
        "id",
        "position",
        "row_source",
        "sections",
        "sheet_key",
        "step_key",
        "template_version_id",
        "tenant_id",
        "title",
    }
)
INSERT_COLUMNS["template_sheet_views"] = frozenset(
    {
        "filters",
        "group_by",
        "id",
        "name",
        "position",
        "sheet_definition_id",
        "sort",
        "template_version_id",
        "tenant_id",
        "view_key",
        "visible_columns",
    }
)
INSERT_COLUMNS["template_skill_pins"] = frozenset(
    {"id", "skill_key", "skill_version_id", "template_version_id", "tenant_id"}
)
INSERT_COLUMNS["template_trigger_defaults"] = frozenset(
    {
        "capability_key",
        "condition_value",
        "enabled",
        "event",
        "id",
        "target_ref",
        "template_version_id",
        "tenant_id",
    }
)
INSERT_COLUMNS["template_versions"] = frozenset(
    {
        "based_on_version_id",
        "change_summary",
        "content_pack_release_ref",
        "created_by",
        "effective_from",
        "id",
        "label",
        "methodology_version_id",
        "seq",
        "status",
        "template_id",
        "tenant_id",
    }
)
UPDATE_COLUMNS["engagement_templates"] = frozenset(
    {"engagement_types", "name", "owner_user_id", "service_line"}
)
UPDATE_COLUMNS["scoping_rules"] = frozenset(
    {"conditions", "effect", "group_op", "label", "position", "target_kind", "target_ref"}
)
UPDATE_COLUMNS["template_agent_column_defs"] = frozenset(
    {
        "default_scope",
        "instruction_doc",
        "options",
        "output_type",
        "runs_as_capability",
        "sheet_column_id",
        "skill_key",
    }
)
UPDATE_COLUMNS["template_form_fields"] = frozenset(
    {"classification", "config", "field_key", "form_id", "label", "position", "required", "type"}
)
UPDATE_COLUMNS["template_forms"] = frozenset({"form_key", "position", "title"})
UPDATE_COLUMNS["template_report_template_refs"] = frozenset(
    {"report_template_id", "report_template_version_id", "role"}
)
UPDATE_COLUMNS["template_requests"] = frozenset(
    {
        "group_key",
        "methodology_request_item_id",
        "position",
        "request_key",
        "shown_by_rule_id",
        "step_key",
        "title",
    }
)
UPDATE_COLUMNS["template_sheet_columns"] = frozenset(
    {
        "classification",
        "classification_reason",
        "client_visible",
        "column_key",
        "config",
        "default_value",
        "description",
        "name",
        "position",
        "required",
        "sheet_definition_id",
        "source_binding",
        "type",
        "validation",
    }
)
UPDATE_COLUMNS["template_sheet_definitions"] = frozenset(
    {"position", "row_source", "sections", "sheet_key", "step_key", "title"}
)
UPDATE_COLUMNS["template_sheet_views"] = frozenset(
    {
        "filters",
        "group_by",
        "name",
        "position",
        "sheet_definition_id",
        "sort",
        "view_key",
        "visible_columns",
    }
)
UPDATE_COLUMNS["template_skill_pins"] = frozenset({"skill_key", "skill_version_id"})
UPDATE_COLUMNS["template_trigger_defaults"] = frozenset(
    {"capability_key", "condition_value", "enabled", "event", "target_ref"}
)
UPDATE_COLUMNS["template_versions"] = frozenset(
    {
        "change_summary",
        "deprecated_at",
        "deprecated_by",
        "draft_etag",
        "effective_from",
        "effective_to",
        "fingerprint",
        "label",
        "methodology_version_id",
        "overlay_stats",
        "published_at",
        "published_by",
        "retired_at",
        "status",
    }
)

# K-03-T12 (1011, TASK-8902): template links, rollouts, updates and scoping evaluations
_TABLES_S53_2: frozenset[str] = frozenset(
    {"scoping_evaluations", "template_rollout_actions", "template_rollouts"}
)
_INSERT_ONLY_S53_2: frozenset[str] = frozenset({"scoping_evaluations"})
INSERT_COLUMNS["scoping_evaluations"] = frozenset(
    {"engagement_id", "inputs_hash", "result", "rule_id", "template_version_id", "tenant_id"}
)
INSERT_COLUMNS["template_rollout_actions"] = frozenset(
    {"engagement_id", "id", "rollout_id", "suggested_action", "tenant_id"}
)
UPDATE_COLUMNS["template_rollout_actions"] = frozenset(
    {
        "action",
        "manager_notified_user_id",
        "notified_at",
        "reason",
        "row_version",
        "set_at",
        "set_by",
        "suggested_action",
    }
)
INSERT_COLUMNS["template_rollouts"] = frozenset(
    {"created_by", "from_version_id", "id", "template_id", "tenant_id", "to_version_id"}
)
UPDATE_COLUMNS["template_rollouts"] = frozenset(
    {"completed_at", "started_at", "started_by", "status"}
)
INSERT_COLUMNS["report_template_versions"] = INSERT_COLUMNS[
    "report_template_versions"
] | frozenset({"field_manifest"})  # T-06-T43 (1015, TASK-8912): a form face's field manifest

# The tables this module owns and its insert-only tables after S53 (one definition each).
TABLES: frozenset[str] = _TABLES_PRE_S53 | _TABLES_S53_1 | _TABLES_S53_2
INSERT_ONLY: frozenset[str] = _INSERT_ONLY_PRE_S53 | _INSERT_ONLY_S53_1 | _INSERT_ONLY_S53_2
