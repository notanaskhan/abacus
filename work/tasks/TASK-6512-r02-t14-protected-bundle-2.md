---
id: TASK-6512
title: "R-02-T14: protected bundle 2 — portal.approvals, portal.deliverables, portal.governance_room; notification and email-template kinds"
spec: SPEC-646
acceptance_criteria: [AC-1]  # the row's acceptance (AC-flags)
risk_zone: red
status: in-review
branch: s33-r02-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: R-02-T14
---

## Objective
With every flag off, production responses and the portal bundle are unchanged; with a flag on
for the canary, its routes serve live data.

## Plan (red)
1. `feature-flags/portal.yaml`: three flags (DEC-137 override on the build clock).
2. `portal/approvals_contract.py` (8 routes) and `portal/deliverables_contract.py` (17 routes):
   each route checks its flag first (404 off), then its service (live since R-02-T09, T11, T12)
   or 501 where its build row has not landed.
3. `notifications/catalogue.py`: `client_question_asked`, `uncorrected_misstatements_acknowledged`,
   `tcwg_question_asked` (display kinds; producers with R-02-T15 and T16).
4. `communications/template_keys.py`: `approval_requested` (POR-08) and `governance_letter_sent`
   (POR-15, DF-40); `deliverable_ready` was registered by R-01.
5. Activity catalogue: `client_approval.decided`, `governance_communication.acknowledged`,
   `deliverable.download_issued`, `deliverable.downloaded` rows already exist (S31/S32).
Rollback: revert; flags default off.

## Progress log
- `2026-11-09` — Built; not run (end pass). Partial: the deliverable page image, download, page
  comment and room report/inquiry routes stay 501 behind their flags (their serving code is R-02's
  later rows); the three notification kinds have no producer until R-02-T15/T16.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3112 | R-02's flags, gate order and new kinds | no |
