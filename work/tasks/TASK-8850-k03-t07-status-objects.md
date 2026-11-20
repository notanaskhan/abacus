---
id: TASK-8850
title: "K-03-T07: Templates v2 and sheets status objects"
spec: SPEC-720
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-k03t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: K-03-T07
---

## Objective
status-vocabulary.yaml gains the eight objects with pill variants, 'Superseded' renders only for retired versions, and make generate regenerates StrEnums and status.generated.ts with no drift.

## Done
- status-vocabulary.yaml eight objects
- kernel/_statuses.py + packages/ui status.gen.ts regenerated
- DEC-5847

## Progress log
- `2026-11-20` — Plan (amber): C2 additive; codegen; drift gate at the end pass.
