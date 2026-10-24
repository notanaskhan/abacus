---
id: TASK-1160
title: Incident register in platform — security_incidents with the FTC clock, the firm create route, staff IncidentPropagation and make incident-propagate (Q-02-T33)
spec: SPEC-051
acceptance_criteria: [AC-2]  # SPEC-051 (as TASK-1014); the Q-02 epic ACs proved here: AC-38, AC-39
risk_zone: amber
status: done
epic: Q-02
plan_key: Q-02-T33
branch: s7-small-items-incidents
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"An incident discovered Sep 10 with 500 or more unencrypted consumers reads notify by Oct 10, and a propagated Accrued incident appears in each affected firm's register with Accrued's facts." Q-02 AC-38, AC-39; §4.2 (`NNNN_security_incidents`), §4.3, §4.5, §4.6, §4.7, §4.8; OQ-5 (owner `platform`); ADR-097.

## Plan (amber zone)
- **Migration** `0143_security_incidents.py` (down_revision 0133): tenant table `security_incidents` with the §4.2 columns (`ref` `INC-YYYY-NNN`, `title` Confidential, `event_kind`, `discovered_at`, `consumers_affected >= 0`, `unencrypted`, `notification_event` GENERATED from `unencrypted` and `consumers_affected >= 500`, `ftc_notify_by date`, `status`, `source`, `accrued_ref`, `dpa_notice_at`, `created_by`, `created_at`), plus `accrued_confirmed_at` so the 72-hour DPA clock is checkable. Shape CHECKs: a firm entry has a person and no Accrued fields; an Accrued entry has `accrued_ref`, `accrued_confirmed_at` and `dpa_notice_at` and no person. `UNIQUE (tenant_id, ref)` and `UNIQUE (tenant_id, accrued_ref)` (propagation is repeat-safe). A guard trigger binds `created_by` to the session's human actor for a firm entry and requires the system actor for an Accrued one. Forced RLS (`tenant_table`); the app inserts named columns only, no update or delete (G-02-T18 grants status changes with its decisions). Rollback: `alembic downgrade 0133`.
- **Service** `platform/incidents.py`: `incident_clock(discovered_at, zone)` (calendar days in the firm's zone, no business-day roll; I-CLOCKS), `clock_day`, `record_incident(ctx, facts)` (flag, `authorise("incident.manage")` on the firm, the next `INC-<year>-NNN` under a per-firm transaction lock, audit `incident.recorded`, event `incident.recorded`), `propagate_into(tenant_id, accrued_ref, facts, staff_id)` (system actor, idempotent on `accrued_ref`, `dpa_notice_at` = the write, audit `incident.propagated`, event `incident.propagated`), `start_propagation(...)` (flag on for every named firm, else 404; dispatches the workflow).
- **Routes** `platform/incident_routes.py`: `POST /v1/firm/security/incidents` (`incident.manage`, 201) and staff `POST /v1/platform/incidents/{accrued_ref}/propagate` (`STAFF`, reason required, 202).
- **Workflow** `IncidentPropagation` (`incident_propagate:<accrued_ref>`, time_sensitive) in `platform/workflows.py`, activity `platform.propagate_incident` (`platform/incident_activities.py`), inputs in `workflow_types.py`; v1 replay history recorded by `abacus_tools.workflows.record_incident_propagation`; `tests/workflows/test_incident_propagation_replay.py`.
- **CLI** `abacus_tools/incidents.py` and `make incident-propagate` (staff-run RB-27 path; dispatches the same workflow; `--dry-run` prints the plan).
- **Identity:** `security_admins(tenant_id)` and `partner_members(tenant_id)` recipient helpers (exported from `identity.api`).
- **Notifications:** `incident.recorded` → `incident_recorded` (QI and partner-level members, never the recorder); `incident.propagated` → `incident_from_accrued` (QI and firm admins). Kinds already registered (Q-02-T30); email text stays database rows.
- **Closed lists:** platform registry `TABLES`/`INSERT_ONLY`; audit target `security_incident` (firm level); route introspection; 202 routes; tenant-isolation table list; schema-check expectations; the catalogue tests.
- **Contract:** `docs/contracts/security-incidents.md` v0.1 (live behind `compliance.incidents`); register row; `make regenerate`.
- **Tests:** `tests/unit/platform/test_incident_clock.py` (AC-38 clock), `tests/integration/test_security_incidents.py` (AC-38 route and 500-consumer rule, AC-39 propagation into three firms with Accrued's facts, the system actor, `dpa_notice_at` within 72 hours, idempotence, flag off 404, non-QI 403, tenant isolation), the catalogue fan-out unit test.

## Progress log
- 2026-10-24: plan written; building.
- 2026-10-24: built. Migration 0143 (down_revision 0133); routes `POST /v1/firm/security/incidents` (`incident.manage`, 201) and staff `POST /v1/platform/incidents/{accrued_ref}/propagate` (`STAFF`, 202); `IncidentPropagation` (time_sensitive) with its v1 history; `make incident-propagate`; contract `docs/contracts/security-incidents.md` v0.1; DEC-290. Tests: `tests/integration/test_security_incidents.py` (6), `tests/unit/platform/test_incident_clock.py` (11), `tests/unit/tools/test_incidents_cli.py` (7), `tests/workflows/test_incident_propagation_replay.py` (3), the catalogue test. Audit `Ref` keys are lower-case letters and underscores only (`reason_sha256` was refused; now `reason_hash`). The recipient helpers joined banned_patterns' LIST_EXEMPT beside `active_firm_admins`. Left for others: G-02's reads, status words and `incident.decide`; RB-27 itself (Q-02-T51); the T38 stub fixtures.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-290 | Ref numbering, the 72-hour fields, the flag on the staff route and `incident.recorded` outside the human-only register are not fixed by the plan | No |
