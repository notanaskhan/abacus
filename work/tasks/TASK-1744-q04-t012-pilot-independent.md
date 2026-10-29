---
id: TASK-1744
title: Q-04-T012 Independent AC tests for the flag calendar, pilot tables and metrics workflow
spec: SPEC-403
acceptance_criteria: [AC-10]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T012
branch: s14-q04-t012
created: 2026-10-29
updated: 2026-10-29
---

## Objective
ADR-078 independent tests for c05 (Q-04-T005 flag calendar), c07 (Q-04-T007 pilot tables) and c08
(Q-04-T008 metrics workflow). Acceptance (backlog row): "Tests prove snapshot immutability, that
rerunning a week writes no duplicate row for NULL-subject metrics (w4, w5, w6, inv_*), the
system-of-record guard and metric arithmetic on edge weeks, and fail when a rule is weakened."
Q-04 AC-8.1 to AC-8.4 for the pilot rows; SPEC-403 AC-10 for the calendar.

## Plan (amber, tests plus the defects they found)
- `backend/tests/unit/tools/test_q04t012_flag_calendar_independent.py`: window first/last days and
  a season's trailing deadline week; weakened exceptions refused; `--check` names flag, date and
  window; calendar order, last train, 21-day edge, "none left", CONFLICT.
- `backend/tests/integration/backfill/test_q04t012_pilot_metrics_independent.py`: app role cannot
  update or delete snapshots; rerun keeps first numbers; NULL-subject duplicates refused by the
  owner; NULLS NOT DISTINCT in the key; system-of-record CHECK, service order, active-member
  confirmer; enrolment windows touching the week; W6 bounds and even-count median; ratio rounding;
  zero denominators; baselines 0 and none; the New Year week; forced RLS and cross-tenant reads.
- Fixes (ED-251): `platform/pilots.py` records modes by number in the audit `Ref`;
  `abacus_tools/pilots.py` refuses a confirmer who is not an active member (one event loop).
- `banned_patterns`: the integration suite joins the TENANT-001 and DB-001 test exclusions.
- DEC-834.
- Rollback: revert the branch.

## Progress log
- `2026-10-29` — Written and run: unit 26 passed; integration 25 passed, with T007 and T008's
  suites still green (31 with T012's integration file). Found ED-251 (both pilot commands failed on
  the audit `Ref`; any UUID could confirm the system of record); fixed here. ruff, pyright,
  lint-imports and banned patterns clean.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** A-02-T32.
