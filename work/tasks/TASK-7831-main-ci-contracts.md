---
id: TASK-7831
title: "Main CI after lo39: make ci-contracts green (const widening, tax v1 proposal_id, built-route stubs)"
spec: SPEC-000  # CI repair
acceptance_criteria: [AC-1]  # make ci-contracts and tests/contracts pass on main
risk_zone: amber  # a quality gate's rule and a frozen contract's field
status: in-review
branch: ci-contracts-const-enum
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39-rec
created: 2026-11-13
updated: 2026-11-13
plan_key: F-01-T05
---

## Objective
Main CI run 43452986801 (f62b1ec3a, the lo39 merge) failed `stage 2 schema and api-client`; the unit
shards were cancelled behind it. Make `make ci-contracts` and `tests/contracts` pass on today's main.

## Plan
- `abacus_tools.contracts`: a `const` field is a one-member enum (DEC-4823).
- `tax_workbook` v1: restore `proposal_id` (DEC-4824); `PickOutcome.mapping_set_id`; the web fixture;
  `make generate`.
- Stub tests: mark the routes S40 and S41 built (tax line picker, Workbench sessions, Today reads).
- Rollback: revert the commit.

## Progress log
- 2026-11-13: built. `contracts --check` clean; `tests/contracts` all pass (8,702 locally, -n 4);
  line-picker unit tests, TXP-02 and fixture handshake tests pass; ruff, pyright, tsc clean.

## Decisions made during this task
- DEC-4823, DEC-4824.
