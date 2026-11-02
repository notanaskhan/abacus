---
id: TASK-3006
title: A-04-T18 risk approval card and G4 facts
spec: SPEC-620
acceptance_criteria: [AC4.3, AC4.4]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T18
branch: s25-a04-t18 (stacked on s25-a04-t19)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"After Margaret decides at 4:40 PM R3 reads Approved, R5 Rebuttal approved and every row EP
approved, Northwind's G4 is met, and a later edit to R4 reopens G4 with a blocker."

## Plan (amber)
- `assurance/risks.py`: `significant_risk` kind (provider, applier), `request_approval`, `rows_of`.
- `assurance/planning_gate.py`: `g4_facts`; exported from `assurance.api`.
- `events.RiskRegisterApproved` (`risk_register.approved`); route served.
- No migration (0613 has `status` and `approved_card_id`). Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| One card over R3 and R5; 409 nothing pending | `test_a04t18_risk_approval.py::test_ac4_3_*` |
| Partner approves, senior 403; G4 blockers; R4 edit reopens | `test_ac4_4_*` |

## Progress log
- 2026-11-02: built. Tests at the S25 end review.

## Decisions made during this task
DEC-2056.
