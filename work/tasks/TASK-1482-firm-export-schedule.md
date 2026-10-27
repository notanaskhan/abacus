---
id: TASK-1482
title: Firm data export schedule and its dual approval (G-02-T19; ADM-06 a, c)
spec: SPEC-349
acceptance_criteria: [AC-25, AC-45, AC-46, AC-47]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T19
branch: s12-gov
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The monthly firm export schedule (1st, 02:00 firm time), approved once by a `security_admin` and a
partner, distinct (DEC-72), running on a Temporal Schedule through `kernel.dispatch`.

## Plan
- **Migration 0241**: `firm_export_schedules` (tenant PK, forced RLS, CHECKs for the one cadence,
  the two approvals distinct, status, a person's act by trigger).
- **Service** `evidence/firm_export_schedule.py`: read, set (`firm_export_schedule.updated`;
  any change resets both approvals), approve (`firm_export_schedule.approved`; 409
  `approver_must_differ`); active: a per-firm calendar Schedule `firm_export_schedule:<tenant>`
  (new `kernel.dispatch.firm_schedule`, a calendar spec in the firm's zone, overlap SKIP);
  paused or pending: the Schedule is paused.
- **Run**: `FirmExportScheduleWorkflow` (batch) notifies both approvers per run. Q-02-T43's
  `FirmExportWorkflow` and `firm_exports` are not on main: the run starts the export through a
  registration slot that Q-02-T43 fills; until then it records `firm_export_schedule.run_skipped`
  and notifies nobody (DEC-623). The History tray is Q-02's list (still a stub).
- **Rollback**: revert; downgrade 0241; delete the per-firm Schedules.

## Progress log
- 2026-10-27: plan written; built.
- 2026-10-27: built and tested, partial: the schedule, its dual approval and the firm's calendar Schedule (`kernel.dispatch.firm_schedule`) are live; each run records `run_skipped` until Q-02-T43 registers the firm export starter (DEC-623), so per-run notifications and the History tray (Q-02's list, still a 501 stub) wait for Q-02-T43.
