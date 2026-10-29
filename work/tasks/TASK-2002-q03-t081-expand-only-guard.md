---
id: TASK-2002
title: Q-03-T081 Expand-only migration guard
spec: SPEC-403
acceptance_criteria: [F4]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T081
branch: s15n-q03-t081
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The one implementation of the expand-only rule from Tue Jun 1, 2027 (DEC-06, ADR P-38 end,
ADR-091 strict; Q-03 F4): a stage-1 check refusing contract operations in a PR's new migrations
unless labelled `contract-step`, and a window mode Q-04-T003's release gate calls (DEC-1052).

Acceptance (backlog row): "A migration with a DROP after Jun 1 fails stage 1 unless labelled
contract-step with both approvals, the same labelled migration fails in window mode on a simulated
in-window date, and the rehearsal completes inside the deploy budget."

## Plan (red)
- `backend/src/abacus_tools/quality/expand_only.py` (new): detection over `upgrade()` (SQL strings
  and `op.*` calls), the verdict (`judge`), `new_migrations(base)` (git diff), the CLI (`check`,
  `window`).
- `abacus_tools/release.py`: `window_gate(..., migrations=)` runs the guard in window mode;
  `window-gate --migrations-base REF`.
- `.github/workflows/ci.yml` stage 1: full-history checkout; a PR step passes the base SHA and the
  PR's labels. `pyproject.toml`: S603/T20 ignore (runs git diff).
- Solo edition: the label is the exception; no second approval (AMENDMENT-solo item 2).
- No migration, flag or route.
- Rollback: revert the branch; nothing else reads the guard.

## Not done here
- The rehearsal on production-sized synthetic data on the perf stack: an ops run once the perf
  stack exists (Q-03-T036's stack is not provisioned); recorded in DEC-1052.

## Acceptance
| Check | Test |
|---|---|
| DROP after Jun 1 refused without the label, passes with it, inert before | `test_ac1_*` |
| Window mode refuses the labelled step; expand-only passes | `test_ac2_*` |
| Each pattern; expand operations pass; enum value removal | `test_each_contract_pattern_is_found`, `test_expand_operations_pass`, `test_an_enum_*` |

`backend/tests/unit/quality/test_expand_only.py`. Independent tests: Q-03-T082.

## Progress log
- 2026-10-29: built (S15 build-now block). The unit file ran once (21 passed, 1 s); the guard ran
  over migrations 0093 (a `BEFORE TRUNCATE` trigger false positive found and fixed) and 0270
  (its `SET NOT NULL` found, as it should be).
