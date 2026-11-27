---
id: TASK-9036
title: "T-08-T29: Eval cases for two_year, planning_screen, amendment and bba_route"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s54-t08-t28-t29-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-08-T29
---

## Objective
Expert-labelled synthetic returns, adversarial client documents, consent-refusal properties, number-provenance and banned sales-language checks.

## Done
- Each section has cases, includes instruction-in-document cases, and passes its frozen gate on the fake model
- REST: a tax reviewer labels and signs; nightly real run after bedrock clearance

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6040 with the season_planner suite (shared module).
