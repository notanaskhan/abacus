---
id: TASK-6118
title: "P-10-T18 independent tests for sessions, realtime events, the minute ledger and the runtime states (T04 to T07)"
spec: SPEC-000  # row (P-10-T18)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: P-10
plan_key: P-10-T18
branch: s30-p10-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-078 tests: RLS, insert-only session items, the 24 h prune, ledger insert-only and integer footing, registry coverage.

## Plan
- `tests/integration/test_p10t18_runtime_tables_independent.py` on a round-trip database: RLS forced on six tables; session items and the minute ledger grant no UPDATE/DELETE and carry their immutability triggers; sessions are never deleted by the app and carry the soft-delete trigger; `prune_realtime_events` refuses a person, another system job and an agent claiming the prune's name; rollup minutes are stored integers and Dec 2027's five capabilities foot to 14,920; the status registry carries the 14 run states and labelled step, session and question states; the glossary names the runtime terms.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
None.
