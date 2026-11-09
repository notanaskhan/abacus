---
id: TASK-6514
title: "R-02-T16: governance room part 2 — private inquiries (addressee only) and released reports"
spec: SPEC-646
acceptance_criteria: [AC-29, AC-30]
risk_zone: amber
status: in-review
branch: s33-r02-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: R-02-T16
---

## Objective
Victoria Lam's two inquiry answers are readable only by the audit team, never by Robert Haines and
never by Dana Kowalski under either of her grants.

## Plan (amber)
1. `assurance/governance_room.py`: `room_inquiries` (a current member of the open room; A-04's
   `fraud_inquiries` addressed to the reader's member contacts; questions through T-02's
   `portal_questionnaire`, whose own addressee check holds) and `room_reports` (C10's released
   deliverables whose audience is the room).
2. `reporting/api.py`: `released_for_audience` (newest version not a draft).
3. `portal/deliverables_contract.py`: `GET …/rooms/{id}/inquiries` and `…/reports` live behind
   `portal.governance_room`.
Rollback: revert; no migration.

## Progress log
- `2026-11-09` — Built; unit tests written, not run (end pass). Answers stay on T-02's
  addressee-only routes; the audit team reads them through A-04.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3114 | Inquiry and report privacy in the room (DEC-93) | no |
