---
id: TASK-6513
title: "R-02-T15: the uncorrected-misstatements acknowledgement kind on A-06's frozen SUM snapshot"
spec: SPEC-646
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
branch: s33-r02-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: R-02-T15
---

## Objective
Dana's acknowledgement stores 22,250 taken from the snapshot with no client-side arithmetic.

## Plan (amber)
1. `assurance/uncorrected_ack.py`: the C18 provider for `uncorrected_misstatements` — items are
   the work item's newest `rep_letter_attachment` SUM snapshot; the net effect is the snapshot's
   frozen `iron_curtain` total; `decide` (acknowledge only, the seen hash unchanged) inserts the
   insert-only, human-only row (0710) with the snapshot's engine version, inputs hash and the
   passed entries, emits `uncorrected_misstatements.acknowledged` and audits it.
2. `assurance/api.py` registers it; `notifications/catalogue.py` fans the event to the EP and
   managers (`uncorrected_misstatements_acknowledged`, R-02-T14's kind).
Rollback: revert; no migration.

## Progress log
- `2026-11-09` — Built; unit tests written, not run (end pass). Partial: the portal Home sources for
  approvals and deliverables (flag-gated to-dos), the approval-request email send on
  `client_approval.requested` from the DB template, and the `client_entries_journal` C11 kind for
  "Download entries" are not built here (carry to S34 with R-02's remaining rows).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3113 | Which snapshot, which total and which entries the acknowledgement stores | no |
