"""The platform module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    # Q-01-T19 (ADR-157): global, no app privileges; through definer functions only.
    {"platform_controls", "platform_control_changes", "firm_provisioning_requests"}
    # F-03-T28 (ADR-148): plans (global) and the firms' module entitlements (read-only to the app).
    | {"plans", "tenant_entitlements"}
    | {"plan_modules"}  # Q-01-T45 (0107)
    | {"security_incidents"}  # Q-02-T33 (0143): the firm's incident register
    | {"incident_propagations"}  # Q-02-T33 (0143): global staff record; definers only
    # G-02-T18 (0240): the register's timeline, two-person decisions and clock reminders.
    | {"security_incident_timeline", "security_incident_decisions"}
    | {"security_incident_reminders"}
    # G-02-T20 (0242): Pub 4557 definitions (global, definers only), the firm's record, its
    # control statuses and its WISP pack jobs.
    | {"safeguards_controls", "safeguards_programs", "safeguards_control_statuses"}
    | {"safeguards_control_set_log"}  # global staff record; definers only
    | {"wisp_packs"}
    | {"pilot_enrolments", "pilot_metric_snapshots"}  # Q-04-T007 (0276): pilot enrolments
    # K-02-T03 (0400, ADR-300): the global reference sets; definers only.
    | {"reference_sets", "reference_set_versions", "reference_set_publications"}
    # P-10-T06 (0684, ADR-148): agent-minute metering.
    | {"agent_minute_ledger", "engagement_agent_budgets", "usage_month_rollups"}
    # F-08-T13 (1001, DEC-5845): presence heartbeats, UNLOGGED and ephemeral (kernel.ephemeral).
    | {"presence_heartbeats"}
    # P-02-T05 (0840, ADR-241): the firm search index and the people's recents (C15 v1).
    | {"search_documents", "search_recents"}
    # G-04-T04 (0920, DEC-5204): plan & usage and support (tenant), and the console's global
    # content, status, directory and platform log (definers only).
    | {"plan_entitlements", "usage_alert_policies", "usage_alert_rules", "usage_alert_events"}
    | {"plan_change_requests", "support_conversations", "support_messages"}
    | {"support_conversation_reads"}
    | {"help_articles", "status_components", "status_incidents", "status_incident_updates"}
    | {"platform_regions", "platform_settings", "platform_tenant_directory"}
    | {"platform_audit_events"}
)
# Insert and read, never update or delete, for the app role (ADR-004).
# G-02-T18 (0240): an incident's status changes only with its decisions (column grants and the
# `security_incidents_decided` trigger), so it is no longer insert-only.
INSERT_ONLY: frozenset[str] = frozenset(
    {"platform_control_changes", "incident_propagations"}
    | {"pilot_metric_snapshots"}  # Q-04-T007 (0276): computed, never rewritten
    | {"security_incident_timeline", "security_incident_decisions"}
    | {"security_incident_reminders"}
    | {"safeguards_control_set_log"}
    | {"agent_minute_ledger"}  # P-10-T06 (0684): one row per run, by trigger
    # G-04-T04 (0920): versions, once-per-month crossings, messages, incident updates, the log.
    | {"plan_entitlements", "usage_alert_events", "support_messages"}
    | {"status_incident_updates", "platform_audit_events"}
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "agent_minute_ledger": frozenset(
        {"tenant_id", "usage_month", "run_id", "engagement_id", "work_item_ref", "service_line"}
        | {"definition_id", "capability", "phase", "minutes", "agent_ms", "cost_usd"}
        | {"run_number"}  # P-10-T42 (0810)
    ),
    "engagement_agent_budgets": frozenset(
        {"tenant_id", "engagement_id", "minutes_per_usage_month", "alert_pct"}
    ),
    "usage_month_rollups": frozenset(
        {"tenant_id", "usage_month", "service_line", "engagement_id", "capability", "phase"}
        | {"minutes", "cost_usd"}
    ),
    "security_incident_timeline": frozenset(
        {"tenant_id", "incident_id", "occurred_at", "code", "facts", "note", "source"}
        | {"author_user_id"}
    ),
    "security_incident_decisions": frozenset(
        {"tenant_id", "incident_id", "kind", "seat", "decided_by", "waiting_for", "note"}
    ),
    "security_incident_reminders": frozenset({"tenant_id", "incident_id", "day"}),
    "safeguards_programs": frozenset(
        {"tenant_id", "qi_user_id", "wisp_name", "wisp_evidence_item_id", "wisp_approved_by"}
        | {"wisp_approved_on", "annual_report_last_on", "annual_report_next_due_month"}
        | {"access_review_quarter", "access_review_due_on", "access_review_status"}
        | {"training_completed", "ptin_attested", "ptin_total", "updated_by"}
    ),
    "safeguards_control_statuses": frozenset(
        {"tenant_id", "control_key", "status", "due_on", "scheduled_on", "evidence_item_id"}
        | {"note", "updated_by"}
    ),
    "wisp_packs": frozenset({"id", "tenant_id", "requested_by"}),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "engagement_agent_budgets": frozenset({"minutes_per_usage_month", "alert_pct"}),
    "usage_month_rollups": frozenset({"minutes", "cost_usd"}),
    # G-02-T18 (0240): only with both decisions (the trigger).
    "security_incidents": frozenset({"status", "closed_at", "notification_started_at"}),
    # G-02-T20 (0242): edited in place against `version` by the QI; never deleted.
    "safeguards_programs": frozenset(
        {"qi_user_id", "wisp_name", "wisp_evidence_item_id", "wisp_approved_by"}
        | {"wisp_approved_on", "annual_report_last_on", "annual_report_next_due_month"}
        | {"access_review_quarter", "access_review_due_on", "access_review_status"}
        | {"training_completed", "ptin_attested", "ptin_total", "updated_by", "version"}
        | {"updated_at"}
    ),
    "safeguards_control_statuses": frozenset(
        {"status", "due_on", "scheduled_on", "evidence_item_id", "note", "updated_by"}
        | {"updated_at"}
    ),
    # Completed once by the system (the trigger).
    "wisp_packs": frozenset(
        {"status", "document_count", "segment_count", "bundle_bytes", "failure_code"}
        | {"expires_at", "updated_at"}
    ),
}

# Q-04-T007 (0276): pilot enrolments and their metric snapshots.
INSERT_COLUMNS["pilot_enrolments"] = frozenset(
    {"tenant_id", "work_item_id", "window_start", "window_end", "baseline_days", "created_by"}
)
INSERT_COLUMNS["pilot_metric_snapshots"] = frozenset(
    {"tenant_id", "enrolment_id", "metric_key", "subject_id", "period_start", "period_end"}
    | {"value"}
)
UPDATE_COLUMNS["pilot_enrolments"] = frozenset(
    {"mode", "confirmed_by", "confirmed_at", "updated_at"}
)

# G-04-T04 (0920, DEC-5204): plan & usage and support; the migration's column grants.
_G04_INSERTS = {
    "plan_entitlements": (
        "tenant_id plan_code term_start term_end renewal_on usage_month_anchor_day"
        " included_agent_minutes seats_total library_channel policy_principal_available"
        " valid_from changed_by_staff change_reason plan_request_id"
    ),
    "usage_alert_policies": (
        "tenant_id at_100_behaviour engagement_default_minutes engagement_alert_pct"
        " billing_contact_user_id partner_approver_user_id updated_by"
    ),
    "usage_alert_rules": (
        "tenant_id level threshold_pct enabled recipient_user_ids recipient_groups"
    ),
    "usage_alert_events": (
        "tenant_id scope rule_id engagement_id usage_month threshold_pct crossed_at"
        " minutes_at_crossing sent_to"
    ),
    "plan_change_requests": (
        "id tenant_id kind from_value to_value modules_add effective_from reason requested_by"
        " approver_user_id"
    ),
    "support_conversations": "id tenant_id user_id",
    "support_messages": (
        "tenant_id conversation_id author_kind author_user_id staff_subject body"
        " related_article_slug"
    ),
    "support_conversation_reads": "tenant_id conversation_id reader_kind last_read_at",
}
_G04_UPDATES = {
    "usage_alert_policies": (
        "version at_100_behaviour engagement_default_minutes engagement_alert_pct"
        " billing_contact_user_id partner_approver_user_id updated_by updated_at"
    ),
    "usage_alert_rules": "enabled recipient_user_ids recipient_groups updated_at",
    "plan_change_requests": (
        "status decided_by decided_at decline_reason applied_by_staff applied_at"
        " plan_entitlement_version_id version"
    ),
    "support_conversations": (
        "status last_firm_message_at last_staff_message_at assigned_staff_subject"
    ),
    "support_conversation_reads": "last_read_at",
}
INSERT_COLUMNS.update({table: frozenset(cols.split()) for table, cols in _G04_INSERTS.items()})
UPDATE_COLUMNS.update({table: frozenset(cols.split()) for table, cols in _G04_UPDATES.items()})
# F-08-T13 (DEC-5845): one row per person and object, replaced by each heartbeat.
INSERT_COLUMNS["presence_heartbeats"] = frozenset(
    {"tenant_id", "user_id", "object_kind", "object_id", "anchor_kind", "anchor_key", "seen_at"}
)
UPDATE_COLUMNS["presence_heartbeats"] = frozenset({"anchor_kind", "anchor_key", "seen_at"})
