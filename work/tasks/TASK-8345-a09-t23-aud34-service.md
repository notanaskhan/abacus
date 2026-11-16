---
id: TASK-8345
title: "A-09-T23: AUD-34 live: group materiality card, component edits, coverage and the workbook"
spec: SPEC-658
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
branch: a09-t23-aud34-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T23
---

## Objective
Spec section: SPEC-658 F5 (AC-5.1 to AC-5.3). AUD-34 live: group materiality card, component edits, coverage and the workbook.

## Plan (amber)
1. `assurance/group_scoping.py`: the EP-reserved C1 kind `group_materiality` whose options are code's (A-04's `firm_policy` over the consolidated Level 1 total assets, or net income for an earnings benchmark; PM 75%, the policy's CT); the decided option recomputed on read.
2. `GET …/group-scoping` (decision, options, components with code's PM share, the total component PM, coverage of total assets by planned work), `GET …/group-scoping/export.xlsx`, `PUT /v1/components/{id}` (If-Match; 422 `component_pm_invalid` at or above group PM, before a decision, or on Analytical only), `POST …/decisions/group-materiality` (raises the card; deciding is P-04's).
3. `group_tb.levels_for` for a tenant-scoped caller (the card provider).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5330). Lint, pyright and the banned patterns clean; the app imports; client regenerated. Partial: Remind, `make_reference` (A-09-T27), the recommender mode hook and a reassess for the card when the consolidation changes; coverage by third-party sales. Gates and
  tests run once at the S47 end pass (build first, test last).
