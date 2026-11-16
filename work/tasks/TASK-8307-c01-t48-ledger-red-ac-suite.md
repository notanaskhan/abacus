---
id: TASK-8307
title: "C-01-T48: Independent AC tests (ADR-078) for the red CAS ledger work"
spec: SPEC-655
acceptance_criteria: [AC-32, AC-33, AC-34]
risk_zone: red
status: in-review
branch: c01-t48-ledger-red-ac-suite
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T48
---

## Objective
Spec section: docs/specs/SPEC-655-c01-close-engine-v1.md §4 F5.
Independent AC tests (ADR-078) for the red CAS ledger work.

## Plan (red)
1. `tests/unit/connections/test_c01t48_red_rules_ac_suite.py` (`ac-test-author: ayushkbhatia`): CONN-001 by AST over `connections`, `closes` and `ledger` (no HTTP write verb on any client; router decorators excluded), the QBO connector declares no write method, business-hours cadence (weekdays 07:00 to 19:00 firm time, hourly tick, next opening inside hours).
2. `tests/integration/test_c01t48_snapshots_ac.py`: monthly snapshots and register rows refuse UPDATE and DELETE to the app role; another tenant sees neither (RLS).
3. Already proven by the implementer suites and not repeated: CDC idempotence, throttle back-off, needs_reauth and meter-budget pauses (`test_c01t16_qbo_v2.py`, `test_c01t17_ledger_sync.py`); replay histories run at the end pass.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. The unit file ran green while building (11 tests); the Postgres file runs at the end pass. Partial: the nightly sandbox conformance run needs Intuit sandbox credentials (human). Gates and
  tests run once at the S47 end pass (build first, test last).
