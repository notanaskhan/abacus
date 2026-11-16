---
id: TASK-8343
title: "A-09-T19: AUD-33 live: the consolidated TB, lock and reopen, the workbook and the elimination routes"
spec: SPEC-658
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
branch: a09-t19-t20-aud33-routes
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T19
---

## Objective
Spec section: SPEC-658 F4 (AC-4.1 to AC-4.5); A-09-T19 and A-09-T20 rests. AUD-33 live: the consolidated TB, lock and reopen, the workbook and the elimination routes.

## Plan (amber)
1. `assurance/group_tb.py`: each entity's TB of record mapped by C9 v2 (net per FS line, debits positive) and the posted eliminations into `ledger.api.consolidate`; level 1 every entity, level 2 the first level-2 entity with entities under it and those; an unmapped entity is left out and counted.
2. `GET …/tb` (code's columns, totals, tie and attribution; one entity's column with `view=entity:<id>`), `GET …/export.xlsx` (every level a sheet), `POST …/lock`, `POST …/reopen` (reason kept on `consolidation_events`) through ledger's new `lock_consolidation`, `reopen_consolidation`.
3. Eliminations: list, create, edit (old lines zeroed and new appended: lines are never deleted; If-Match), approve one and many, apply (post to the consolidation layer), reject with a sealed reason (`adjustments.decisions.reject_with_note`).
4. `ledger.api` exports the engine under its own names; `TrialBalanceSummary` gains `client_entity_id` (additive).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5328). Lint, pyright and the banned patterns clean; the app imports; client regenerated. Partial: the consolidation's own C3 reviewable and export section, and reopen staling its sign-offs and AUD-34's coverage facts; the intercompany tally reads `pending`. Gates and
  tests run once at the S47 end pass (build first, test last).
