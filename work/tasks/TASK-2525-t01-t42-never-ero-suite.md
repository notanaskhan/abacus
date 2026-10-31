---
id: TASK-2525
title: T-01-T42 Never-ERO and transmitter suite
spec: SPEC-501  # AC-13, AC-14; T-01 §3.15
acceptance_criteria: [AC-13, AC-14]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T42
branch: s20c-t01-t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
`backend/tests/security/test_never_ero_transmitter.py` plus I-AGENT-NEVER rows: no code path
transmits a return or a 1099, NEVER-ERO-001 holds, no IRS or state DOR host on the egress
allowlist, export files are never sent by Accrued, `transmission.record` human-only at five
layers, and the agent principal denied the tax decisions and `consent.*`.

Acceptance (backlog row): "The suite is a required check before Tue Aug 17, 2027 and fails on a
planted outbound call to an IRS host."

## Plan (red)
- The suite (static and generated-matrix checks; the behaviour at each layer is T-01-T37's
  integration test).
- NEVER-ERO-001: read CamelCase names as snake case.
- Required check: it runs in CI stage 2 (`tests/security` in INTEGRATION_TESTS).
- Rollback: delete the suite; revert the rule line.

## Notes
- Stacked on T-01-T37 (`s20c-t01-t37`).

## Progress log
- `2026-10-31` — Built on `s20c-t01-t42`. Suite and banned-pattern tax tests 31 passed.
