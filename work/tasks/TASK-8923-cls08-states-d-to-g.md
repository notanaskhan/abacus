---
id: TASK-8923
title: "C-02-T37: CLS-08 states d, e, f and g; studio as a hidden planned link; lock and reopen confirms"
spec: SPEC-701
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-c02t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T37
---

## Objective
Row acceptance: "CLS-08d, e, f and g render at Tier C and the studio button is absent in every live scenario." Finish CLS-08 d (Released, watermark removed), e (Approved by client with Lock close), f (SSARS 27 route), g (No answer with Open letter), the R2 studio button and Studio version row as hidden planned links until A-10, and the lock and reopen confirms.

## Done
- package read fills released_by and client_approved_by and adds approval_requested_from (owner + approver of record)
- d and e status lines; Lock close confirm (close.lock) and Reopen close… with a required reason (close.reopen)
- g: Legend or report per the engagement letter + Open letter (ENG-04 planned link)
- R2 studio button and Studio version row behind PLANNED_VISIBLE (absent in production)
- fixtures and Python scenario export updated
- tests: unit test_c02t37_package_people (3), vitest CLS-08 (14) + CLS-08.live (7: studio absent in every scenario)

## Progress log
- `2026-11-23` — Built d to g with the package people read; unit and vitest green.
