---
id: TASK-7408
title: "T-05-T24: Consumer contract tests (handshake step 1) against the three red-service stubs: adjusted_tb tax layers (C8), the tax form-line taxonomy on mapping sets (C9) and the workbook-run plan provider (C6 v2), as pytest plus TypeScript fixture assertions"
spec: SPEC-651
acceptance_criteria: [AC-1]  # the suites run red against the stubs and turn green when the implementations land
risk_zone: amber
status: in-review
branch: s38-t05-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T24
---

## Objective
The three suites run red against the stubs and turn green only when the implementations land.

## Plan (amber)
- `backend/tests/contracts/t05_consumers/test_t05t24_handshake.py`: what T-05 reads now (C8 entry
  and adjusted-TB fields, the `tje` kind and "TJE" numbering; C9 mapping set and row fields; C6
  v2's `register_run_step` and the workbook run's 202 answer), and what the providers do not carry
  yet as strict expected failures: C8 `atb`/`tje`/`ttb` layers and `account_scope` (T-05-T25), C9
  `taxonomy_kind`, `reference_set_version_id` and `form_line_key` (T-05-T26), the ten run-step
  kinds (T-05-T32). A strict xfail fails on XPASS, so each turns green only when its provider
  lands and the mark is removed (DEC-4407).
- `apps/web/src/fixtures/seed/tax-entity.handshake.test.ts`: the fixture's trial balance states
  tax basis = UTB + AJE + RJE + TJE, TJE nets to zero, 4510-T is tax-only, Run 2's keys are
  published and Run 1 leaves 1300 unmapped; the run plan has the ten tasks.
- Rollback: revert.

## Partial
- "Running in N's CI": the solo edition has one CI; the suites run there at the end pass.

## Progress log
- `2026-11-12` — Built (S38). Backend: 4 pass, 5 strict xfails; web: 6 pass.
