---
id: TASK-2916
title: A-06-T04 migration 0644 assurance_completion
spec: SPEC-642
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T04
branch: s24-a06-t04 (stacked on s24-a06-t03)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-06's completion records: findings rooted on issues, deficiencies, misstatements, SUM snapshots and consultations, beside SPEC-043's tables (DEC-1960).

## Plan

- Migration `0644_assurance_completion` (expand-only, on 0643): `audit_findings` (UNIQUE issue, ref F-nn, sealed why-surfaced, agent findings name their run), `deficiencies` (guard: Concluded or Communicated needs the concluded severity and a human decision on its own card; Communicated needs its date), `audit_misstatements` (refs AJE/RJE/PAJE/BCT/PY/M-n; Passed on SUM names who and why; projected needs its projection), `sum_snapshots` (insert-only), `consultations` (guard: concluded by the person consulted). Forced RLS; no DELETE.
- `assurance/registry.py`: `COMPLETION_TABLES`, insert-only snapshots, insert and update columns.
- Test: `tests/integration/test_a06t04_assurance_completion_migration.py`.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-06-T03. Tests written, not run.
