---
id: TASK-2627
title: N-02-T42 journey E2E for M13 (j06 11, j03 3, j23 3, j12 9)
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T42
branch: s21-n02-t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The four journey steps pass nightly by Fri Aug 20, 2027 with assertInvariants and axe."
(N-02 §10.1, M13.)

## Scope
- J06: j06 11a (Claire on /sign, POR-06 e, "1 of 2 signed") and j06 11b (POR-06 h, the failed
  identity check to a paper form).
- J03: j03 3 (ENG-04 e, the audit letter sent 0 of 2; Dana's Sign area).
- J23 (new file): j23 3 (SIG-01 c Completed; ENG-04 d signed and countersigned).
- J12: j12 9 (POR-06 a review, c signed, d identity questions, g declined).
Every step runs the harness's axe and INV-1 to INV-5.
**Deviation**: the fixture walks use the built artboards, which carry other clients' data than the
named ones (ENG-04 e is Fairhaven's audit letter, not Northwind's; ENG-04 d is Copperleaf's
countersigned letter, not E14 Granite Peak's; POR-06 h is Owen's 8879-PE, not Jonah's). The named
envelopes walk on staging; the hosted runs are `test.fixme` with the M13 owner until then.
Merge note: J06 is also appended by T-02-T32 (#1010); the two tails join at the batch merge.

## Progress log
- 2026-11-01: written; runs at the batch's end review.
