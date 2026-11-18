---
id: TASK-8605
title: "T-08-T06: Migration 0961 tax_practice_tools"
spec: SPEC-710
acceptance_criteria: [AC-35, AC-24, AC-28, AC-29]
risk_zone: amber
status: in-review
branch: t08-t06-tax-practice-tools-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T06
---

## Objective
Spec section: docs/plan/epics/T-08.md §4.2 NNNN_tax_practice_tools. Variance explanation versions and acceptances, standards runs, items, check results and confirmations, planning screens, opportunities and events, amendments, explanation versions, return supersessions, AAR adjustments and elections.

## Plan (amber)
1. migrations/versions/0961_tax_practice_tools.py on 0960: thirteen new tax tables with forced RLS, nine insert-only; acceptances, confirmations and AAR elections human-only bound to app.actor_kind; check results refuse an agent actor; opportunity events need a human for raised, declined and dismissed and a reason for dismissed.
2. T-05 planning_opportunities (0830) widened additively (found on main: the epic assumed a new table): rule rows, six statuses, consent basis, savings and basis, a partial unique (work_item_id, rule_key).
3. tax_return_accepted_frozen: an accepted return's identity fields refuse updates; status, sync and hold stay live.
4. tax/registry.py entries, schema_check IMMUTABLE_TABLES, entity_tri TRI_RECORDS rows.
5. Rollback: downgrade drops the new tables, the trigger and the added columns, restoring 0830's CHECKs.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5605). planning_opportunities already existed (T-05-T28, 0830, memo rows, open only; its docstring says T-08 widens it), so it is altered, not created. Gates and tests run once at the S50 end pass (build first, test last).
