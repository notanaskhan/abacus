---
id: TASK-8360
title: "T-07-T28: Independent tests: the clause verifier, the instrument reader's consent and reach, the CCH 1041 reconciliation"
spec: SPEC-656
acceptance_criteria: [AC-12, AC-13]
risk_zone: red
status: in-review
branch: t07t28-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T28
---

## Objective
Spec section: SPEC-656; T-07-T11, T13, T19. Independent tests: the clause verifier, the instrument reader's consent and reach, the CCH 1041 reconciliation.

## Plan (red)
1. `tests/unit/tax/test_t07t28_independent.py` (13): fabricated clause `source_not_found`; a clause under another instrument or segmentation `locator_invalid` with the word layer never asked; a quote outside the regions `bbox_mismatch`; a superseding instrument moves every old segmentation.
2. Reader: refused `consent_required` before any tool or model call; the output has no action field; settle drops an uncited governed reading and an invented figure; the only write is the proposal tool.
3. CCH 1041: only real differences flag (engine-only 1041 keys included, foreign keys never); one `engine_diagnostic` issue per difference; neither bridge module imports a network client.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. 13 passed; ruff and pyright clean. No finding. Still open on the row: the trustee's beneficiary-return read and the seeded-vulnerable-build runs; the release-gate truth table rests on T-02-T28's suite. Gates and
  tests run once at the S47 end pass (build first, test last).
