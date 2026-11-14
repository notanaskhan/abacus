"""The closes module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {
        "closes",  # F-03-T22 (0089); lifecycle columns C-01-T09 (0881)
        # C-01-T09 (0881): plans, versions, rows, request templates, templates, procedures.
        "close_plans",
        "close_plan_versions",
        "close_plan_rows",
        "close_request_templates",
        "close_templates",
        "close_procedures",
    }
)
INSERT_ONLY: frozenset[str] = frozenset({"close_templates"})
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "closes": frozenset(
        {"tenant_id", "work_item_id", "engagement_id", "period"}
        | {"client_entity_id", "requests_publish_on", "due_on"}
    ),
    "close_plans": frozenset(
        {"tenant_id", "client_entity_id", "template_key", "close_due_business_day", "created_by"}
    ),
    "close_plan_versions": frozenset(
        {"tenant_id", "plan_id", "version", "effective_from", "change_note", "drafted_by"}
        | {"drafted_by_run_id"}
    ),
    "close_plan_rows": frozenset(
        {"tenant_id", "version_id", "position", "account_external_id", "account_name"}
        | {"account_class", "procedure", "method", "evidence_required", "source"}
        | {"review_level", "frequency", "threshold_ref", "drafted_suggestion_id"}
    ),
    "close_request_templates": frozenset(
        {"tenant_id", "version_id", "title", "category_path", "due_business_day"}
        | {"client_visible", "source_row_ids"}
    ),
    "close_templates": frozenset(
        {"tenant_id", "key", "name", "version", "rows", "request_templates", "imported_by"}
    ),
    "close_procedures": frozenset(
        {"tenant_id", "close_id", "run_id", "run_step_id", "plan_row_id", "group_key"}
        | {"account_external_id", "status", "meta", "open_count", "started_at"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "closes": frozenset(
        {"client_entity_id", "status", "on_hold", "on_hold_reason", "close_plan_version_id"}
        | {"plan_pinned_at", "requests_publish_on", "due_on", "run_no", "locked_at"}
        | {"row_version"}
    ),
    "close_plans": frozenset({"template_key", "close_due_business_day"}),
    "close_plan_versions": frozenset(
        {"status", "effective_from", "change_note", "publish_requested_by"}
        | {"publish_requested_at", "published_by", "published_actor_kind", "published_at"}
        | {"row_version"}
    ),
    "close_plan_rows": frozenset(
        {"position", "account_external_id", "account_name", "account_class", "procedure"}
        | {"method", "evidence_required", "source", "review_level", "frequency"}
        | {"threshold_ref", "adopted_by", "adopted_at"}
    ),
    "close_request_templates": frozenset(
        {"title", "category_path", "due_business_day", "client_visible", "source_row_ids"}
    ),
    "close_procedures": frozenset(
        {"status", "meta", "open_count", "failure_code", "started_at", "finished_at"}
    ),
}
