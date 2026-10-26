---
id: TASK-1319
title: Data-layer invariant checker INV-1 and INV-5 (F-04-T30)
spec: SPEC-307
acceptance_criteria: [AC-7, AC-8]
risk_zone: amber
status: in-review
epic: F-04
plan_key: F-04-T30
branch: s10-f04-t30-invariants
created: 2026-10-26
updated: 2026-10-26
---

## Objective
`abacus_tools.harness.invariants`: the data-layer half of the journey harness (F-04.30), with
INV-1's human-only actions derived from the generated `_matrix.py`, and self-tests that fail on
each injected violation (F-04.31).

## Plan
- `backend/src/abacus_tools/harness/invariants.py`: pure `check_inv1`, `check_inv5` over
  `AuditRow`s; `human_only(action)` = the register (`kernel._human_only_actions`) plus every
  audit action an agent-denied matrix action covers (`report.release` covers `report.released`,
  `follow_up.send` covers `follow_up.sent`); `load(conn, tenant, since_seq)`; a loopback-only
  CLI that exits 1 on a violation.
- INV-2, INV-3 and INV-4 stay UI and API checks in `apps/web/e2e/harness/invariants.ts` (what a
  page shows and what a probe answers); the data layer has nothing more to say about them.
- No migration. Rollback: revert.

## Tests (end of the run)
- `backend/tests/unit/harness/test_invariants.py`: an injected agent row of a register action,
  of a matrix-derived action and of a non-human-only action (passes); agent row without
  `on_behalf_of_user_id`; human row with an unknown user; policy row without `policy_ref`; an
  unknown actor kind; a clean window passes. The matrix derivation reads `_matrix.ACTIONS`.

## Progress log
- 2026-10-26: built (build-first).
