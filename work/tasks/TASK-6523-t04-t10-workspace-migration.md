---
id: TASK-6523
title: "T-04-T10: migration 0761_tax_individual_workspace (expand-only)"
spec: SPEC-649
acceptance_criteria: [AC-1]  # the row's acceptance (AC-schema)
risk_zone: amber
status: in-review
branch: s33-t04-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: T-04-T10
---

## Objective
T-04 §4.2's nine tables, expand-only, with forced RLS and the archived guard.

## Plan (amber)
1. `migrations/versions/0761_tax_individual_workspace.py` on 0760: `return_worksheets`,
   `return_worksheet_sections`, `return_fields` (derivation CHECKs: engine needs its key, formula
   needs its code formula id), `document_approvals` (insert-only, human-only by the transaction's
   actor, a reversal once), `k1_activities` (DEC-88 `source_package_id`, one per package),
   `k1_treatments` (decided/override CHECKs) and insert-only `k1_treatment_events` (approve and
   override only by a person), `residency_determinations` (confirmed only by a person through a
   proposal) and insert-only `residency_facts`. Every table carries engagement and the return's
   work item, so the archived guard attaches; no TIN anywhere; TRI as typed JSON.
2. `tax/registry.py`: TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS; tenant-isolation list.
Rollback: downgrade drops the nine tables and the function; nothing else changed.

## Progress log
- `2026-11-09` — Written; up/down/up and refusals run at the end pass. Closes T-04-T03's remainder
  (table owners). Re-chain onto main's head at merge.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3123 | The schema's added CHECKs beyond §4.2 | no |
