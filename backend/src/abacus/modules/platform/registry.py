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
    | {"wisp_packs"}
)
# Insert and read, never update or delete, for the app role (ADR-004).
# G-02-T18 (0240): an incident's status changes only with its decisions (column grants and the
# `security_incidents_decided` trigger), so it is no longer insert-only.
INSERT_ONLY: frozenset[str] = frozenset(
    {"platform_control_changes", "incident_propagations"}
    | {"security_incident_timeline", "security_incident_decisions"}
    | {"security_incident_reminders"}
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
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
