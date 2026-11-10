---
id: TASK-6117
title: "P-10-T17 independent tests for the runtime migrations and the backfill (T02, T03, T14)"
spec: SPEC-000  # row (P-10-T17)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-10
plan_key: P-10-T17
branch: s30-p10-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-078 tests: forced RLS, insert-only, forward-only state, status-state sync for legacy writers, human-only plan decisions and run sign-offs, up/down/up, and the backfill's narrow door.

## Plan
- `tests/integration/test_p10t17_runtime_migrations_independent.py` on a round-trip database: RLS forced with a policy on every runtime table; plans, run events and feedback grant no UPDATE/DELETE; a legacy `status` write sets `state` (escalated → needs_input, reason escalated); a v2 `state` write sets `status` and `finished_at`; illegal transitions refused; cancelled reachable from active states; plan decisions and run sign-offs refused for agent, system and someone else's name (CHECK before FK), passed for the person themself; the 0711 backfill door admits only the legacy mapping and nothing else moving.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
None.
