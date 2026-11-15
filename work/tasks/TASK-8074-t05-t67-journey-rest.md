---
id: TASK-8074
title: "T-05-T67 rest: J08 part 2 (K-1 drafts, declined consent) and T-05-T63/T65's database clauses"
spec: SPEC-651
acceptance_criteria: [AC-13, AC-14]
risk_zone: green
status: in-review
branch: t05-t67-journey-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-05-T67
---

## Objective
Steps 2–4 of TASK-8026, on the same loaded day as part 1 (`tests/integration/tax/test_j08_entity_return.py`).

## Built
- **Step 3 (K-1 drafts):** Ridgeline's five K-1 packages read Draft.
- **Step 4, T-05-T63's database clause:** the TJE layers balance (`adjustments.api.adjusted_tb`,
  `ttb`). Every TJE nets to zero, and TTB foots to ATB.
- **Step 4, T-05-T65's database clauses:**
  - The M-2 fix left the workbook a checkpoint trail with one current (`review.api.list_checkpoints`).
  - A hostile import file (empty, formula injection, binary) is refused with `ImportInvalid`.
- **Step 2, declined consent:** with Ridgeline's signed consents revoked,
  `entity_run_plan.consent_in_force` is false. Every model step of a full plan is a
  `consent_7216` question, and every code step still computes.

## Partial
The CCH round trip (export from the approved checkpoint, an import with 0 differences, a 1-dollar
change raising one `engine_diagnostic`) needs the engine values file's field keys. That is
T-05-T60's CCH Axcess entity layout, which is unvalidated (T-05 OQ-1, human).

## Progress log
- `2026-11-15` — Written (DEC-5060). ruff and pyright are clean; it runs against Postgres at the
  end pass, under the test lock.
