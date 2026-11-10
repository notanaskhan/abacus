---
id: TASK-6722
title: "T-04-T18: evals/tax_return suite skeleton (frozen thresholds, case schema, graders, 31 seed cases)"
spec: SPEC-649
acceptance_criteria: [AC-6, AC-9, AC-11]
risk_zone: red
status: in-review
branch: s35-t04-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T18
---

## Objective
The suite runs on the fake model in CI with every section 6 threshold frozen, and a TRI case without both consents fails unless the tool layer refuses before any model call.

## Plan (red: written before the build)
- `backend/src/abacus_tools/evals/tax_return.py` (new): `FROZEN` thresholds per capability and mode
  (T-04 §6 table verbatim: drafter, analyst `k1_treatments`, `residency`, `explain`, fix runner,
  `tax.assistant`); the case schema on P-10-T34's trajectory format plus `TaxOutput` (field
  changes against labels, net change, draft-K-1 flag, §7216 consents and where the run was
  refused, injections, seeded gaps, residency); thirteen tax graders beside the twelve trajectory
  graders; `load` refuses a `suite.yaml` whose thresholds are not `FROZEN`; per-capability rates
  over pass and adversarial cases (seeded cases prove graders, left out of rates).
- `evals/tax_return/suite.yaml` (new, PROTECTED): the frozen thresholds and 31 seed cases (Feld,
  Shah; 18 pass or adversarial, 13 seeded so every grader has a failing case), including TRI
  without consent for the drafter and the assistant (refused at the tool layer, no model call).
- CLI `--agent tax_return`, `make evals-tax-fast`, a CI step (every run; code only, seconds).
- `docs/product/failure-taxonomy.md`: the tax failure classes.
- Test: `backend/tests/unit/tools/evals/test_t04t18_tax_suite.py`.
- Rollback: revert; nothing in the product imports the suite.

## Notes
- ACs: SPEC-649 transcribes T-04 §3; §6's suite has no AC of its own, so the task names the
  consent ACs its TRI cases hold (AC-6.8, AC-9.3, AC-11.1) and the row's backlog acceptance.
- The `issues.fix_runner` and residency client-wording thresholds the table names as counts
  ("uncited rows 0", "internal terms 0") are frozen as rates of 1.0 on their absence graders.
- Faithfulness judge (explain, ≥ 4 after calibration) and cost (assistant ≤ baseline + 10%) are
  model-run metrics: T-04-T43's real runs, not the fake-model skeleton.
- notanaskhan merges the protected `suite.yaml` (thresholds) per the row.

## Progress log
- 2026-11-10: built; the CLI ran the suite on the fake model: passed, 31 cases, no grader without
  a seeded case. Unit test runs at the S35 end pass.
