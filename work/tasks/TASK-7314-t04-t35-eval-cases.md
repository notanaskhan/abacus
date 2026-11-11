---
id: TASK-7314
title: "T-04-T35: Eval cases complete, labelled with the tax CPA: drafter mapping and self-check, K-1 treatment labels (8 kinds, SALY changes), residency, explain, fix runner, assistant Q&A"
spec: SPEC-649
acceptance_criteria: [AC-9]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: red
status: in-review
branch: s37-t04-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T35
---

## Objective
The suite holds at least 150 labelled cases with sources, every DE-3 to DE-6 class has cases, and
the fake-model run passes the deterministic graders.

## Plan
- `evals/tax_return/cases/t04t35_labelled.yaml` (119 cases; 150 with suite.yaml's 31): K-1
  treatments for the eight kinds × Feld and Shah × SALY held or moved, on AC-7.2's code facts
  (307,900; 61,580; 312,500; 4,674,575; 141,634; 16,025; 1,550); drafter mapping and self-check
  across the Feld, Shah, Okafor and Thornbury households; residency (full year, the 150-day
  conflict, part-year NYC); explain; the fix runner; assistant Q&A; adversarial variants (TRI
  without consent, an instruction in a K-1 statement, pressure to confirm, cross-client).
- `abacus_tools.evals.tax_return`: `Case` gains `source`, `label_status`, `de_classes`; `load()`
  reads `cases/*.yaml` beside the protected suite.yaml and refuses thresholds there.
- Test: `backend/tests/unit/tools/evals/test_t04t35_cases.py`.

## Partial
- Labels are `pending_cpa`: the tax CPA's sign-off is a human step (F-09's engagement).
- Most new cases are labelled variants of T-04-T18's recorded trajectories (same tool sequence,
  new subject and label); the real-model runs that make them independent trajectories are
  T-04-T43's.

## Progress log
- `2026-11-12` — Built (S37). The suite ran once on the fake outputs: 150 cases, passed, every
  grader seeded. Unit test written, run at the end pass.
