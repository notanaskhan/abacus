---
id: TASK-6818
title: "P-10-T41: runtime.conformance eval cases on the J11 and J23 seed; evals/runtime_conformance/suite.yaml thresholds"
spec: SPEC-647
acceptance_criteria: [AC-H4, AC-H2, AC-W1]
risk_zone: red
status: in-review
branch: s36-p10-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-12
plan_key: P-10-T41
---

## Objective
The suite has at least 40 cases with every DE-3 to DE-6 case at threshold 1.0; notanaskhan
approves the protected suite file (the PR).

## Plan (red)
- `evals/runtime_conformance/suite.yaml` (PROTECTED, ADR-079): 61 cases, 20 tagged DE.
- `backend/src/abacus_tools/evals/runtime_conformance.py`: the runner (P-10-T34's twelve graders
  plus `injection_containment`, `asks_when_ambiguous`; per-grader thresholds; DE cases at 1.0;
  min 40 cases; every grader seeded). `__main__` dispatch, `make evals-conformance-fast`, CI stage 3
  step on agent paths. DEC-3412.
- Tests: `backend/tests/unit/tools/evals/test_p10t41_conformance_suite.py`.
- No migration, no flag. Rollback: revert (the spec's `evaluation_suite` path then has no suite).

## Built
Cases on the J11 seed (Brightwater Hale run #4118: 79 open returns, 2,625 records = 224 + 214 +
241 + 1,946, Save to Files for Hannah Leclerc, saved 10 s after approval) and the J23 seed
(Northwind #4127: 14 workpapers 1 + 5 + 1 + 4 + 3, blocked on Margaret Okonkwo, BH-EBP-140 step 8
failure at 9:58, total plan assets 16,812,400). Tool names and arguments are the capability's
registered tools (`specs/v2/runtime.conformance.yaml`).

The suite was validated once on the fake route while authoring (status passed, every rate 1.0);
its unit tests are written and run at the end pass.

## Partial
- Real routes (direct, Bedrock) and the cost row in `evals/baselines.yaml`: P-10-T46 (S37).

## Progress log
- `2026-11-11` — Built (S36). Suite validated once by the runner (authoring check); tests not run.
- `2026-11-12` — The founders approved the protected suite file as merged in #1700 (DEC-3418).
