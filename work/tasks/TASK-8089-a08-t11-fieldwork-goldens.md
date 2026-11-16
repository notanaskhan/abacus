---
id: TASK-8089
title: "A-08-T11: Golden fixtures and Hypothesis properties for the fieldwork engines"
spec: SPEC-657
acceptance_criteria: [F1, F3, F5, F6]
risk_zone: amber
status: in-review
branch: a08-t11-fieldwork-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T11
---

## Objective
ADR-078 goldens transcribed from the seed and screen states, each citing its screen and state,
with properties for footing, determinism and seed reproducibility.

## Built
- `backend/tests/golden/fieldwork/test_a08t11_fieldwork_goldens.py` (11 pass):
  JE scoring AUD-12 a (142 · 38 · 61 · 17 · 9, 236, 34 ≥ 61); properties: scores foot to the
  unique count, reasons iff a score, order-independent with the same inputs hash; selections
  re-draw from the seed. Flux AUD-13 a (8 of 14 = 6 + 2, interest 26.8% within) and AUD-26 a
  (only Grants); property: over only on both legs. Coverage AUD-14 a (15.3%); property: a
  bounded share. Unreconciled AUD-14 drawer (C3 Alpine Ridge ties, below CT); property:
  unreconciled + respondent = books + items, order-independent.
- `backend/src/abacus/modules/assurance/compute/reconciliation.py`: the pure `reconcile`
  (books + items - respondent, to the cent; tie; below CT), for A-08-T18 to call.

## Partial
- MUS goldens wait for the MUS engine (A-08-T13, a later sprint).

## Progress log
- `2026-11-15` — Built.
