---
id: TASK-1481
title: Incident register depth on Q-02's kernel (G-02-T18; ADM-06 a fieldset C, d)
spec: SPEC-349
acceptance_criteria: [AC-21, AC-22, AC-23, AC-45, AC-46, AC-47]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T18
branch: s12-gov
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The register's read side, the append-only timeline and the two-person decisions on Q-02's
`security_incidents`, with FTC clock reminders on days 20, 25 and 29.

## Plan
- **Migration 0240** (`down_revision` 0220): `security_incident_timeline` (insert-only, forced
  RLS; a firm entry is the session's own person's by trigger; `source` firm/system);
  `security_incident_decisions` (insert-only; a person's act by trigger; `UNIQUE (incident, seat)`,
  `UNIQUE (incident, decided_by)`, the first names the second); `security_incidents` gains
  `notification_started_at`, `closed_at`, with the app's UPDATE on `status`, `closed_at`,
  `notification_started_at` only, guarded by a trigger: investigating to closed or a notification
  start only once both seats have decided the same kind; `security_incident_reminders`
  (insert-only, one row per incident and day, so a reminder is sent once).
- **Service** `platform/incident_register.py`: list (P-36 page, `counts` open/closed), detail
  (timeline oldest first, reminders on), append (`incident.timeline_appended`), decide
  (`incident.decision_recorded`, then `incident.decided`); 409 `decider_must_differ`,
  `already_decided`; 422 `second_decider_invalid`. Accrued entries read `source: accrued`.
- **Reminders**: `IncidentClockReminders` Schedule (daily) notifies the QI and the partners
  (`incident_deadline_approaching`) for open notification events on days 20, 25 and 29.
- **Notifications**: `incident_decision_requested` to the named second decider.
- **Registries**: platform registry, schema_check, test_schema_check_db, Schedule exact lists,
  replay history, activity catalogue names, posture source unchanged.
- **Rollback**: revert; downgrade 0240 drops the three tables and the columns.

## Progress log
- 2026-10-27: plan written; built.
