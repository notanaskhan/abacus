---
id: TASK-6005
title: "T-03-T18 retire tax.extensions_estimates and questionnaires.editor for the tax_returns entitlement (held for the Dec 16 batch)"
spec: SPEC-000  # row (T-03-T18)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T18
branch: s29l-t03-flags
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
No T-03 flag remains in the Jan 1-Apr 20 window, and nothing T-03 serves opens to a firm without the tax_returns entitlement.

## Plan
Remove both flags from tax.yaml and requests.yaml and regenerate. schedules_contract._gate and _gate_on_return, questionnaire_editor_contract._gate and _gate_either read `entitlement(ctx.tenant, "tax_returns")` (404 `tax_returns`) where they read the flag. BND-03's editor reads useEntitlement("tax_returns"); its `off` fixture drops the entitlement. Seed: no flag events (tax_board grants the entitlement). Tests: the stub gate test reads the entitlement, the bundle test asserts both flags gone, integration fixtures grant tax_returns. Rollback: revert (flags return default off).

## Progress log
- 2026-11-07: built. tests/contracts/t03/test_t03t02_stub.py and tests/unit/tax/test_t03t01_bundle.py pass with the notices retirement tests (124). Web tsc and eslint clean. Integration fixtures updated; run at the end pass.

## Decisions made during this task
DEC-2605
