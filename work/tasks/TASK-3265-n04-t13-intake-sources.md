---
id: TASK-3265
title: N-04-T13 notice intake sources (answer effect, triage destinations, fail closed)
spec: SPEC-000  # row (N-04 has no SPEC yet)
acceptance_criteria: [AC-13]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T13
branch: s27-n04-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"An inbox item, a portal upload and an organizer Q8 upload each create exactly one intake, and
with the flag off they stay where they were with pending_handler."

## Plan (amber)
- `notices/intake_sources.py`: `route_upload_to_notices` on T-03's answer-effect slot (one
  intake from the upload's evidence version, source `organizer`, named creator the organizer's
  owner; flag off or no file: `HandlerUnavailable`, so the engine records `pending_handler`);
  N-01 triage destinations `notice` (supporting documents onto an open notice's work item) and
  `notice_intake` (the client's permanent file; NOT-01 opens the intake).
- `requests`: `HandlerUnavailable` in the slot and the engine; the engine passes the upload's
  evidence version. `communications.api` exports `IntakeNode`.
- Tests: `tests/unit/notices/test_n04t13_intake_sources.py`.
- Partial: the intake row from a `notice_intake` triage filing needs N-01's post-placement hook
  (the destination files it; the person creates the intake from NOT-01 b).

## Progress log
- 2026-11-04: built. `notice_intakes.source` allows `organizer`, and `created_by` is required,
  so the handler names the organizer's owner.

## Decisions made during this task
DEC-2245.
