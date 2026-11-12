---
id: TASK-7308
title: "T-05-T18: Eval suites part 1: evals/tax_account_mapper and evals/tax_agreement_reader with Brightwater Hale cases, expert labels (pending the tax CPA), adversarial cases; thresholds frozen"
spec: SPEC-651
acceptance_criteria: [AC-T18]
risk_zone: red
status: in-review
branch: s37-t05-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T18
---

## Objective
Both suites exist with frozen thresholds and pass on the fake model before any prompt work
starts.

## Plan (red)
- `backend/src/abacus_tools/evals/tax_entity.py`: case schemas, the deterministic graders and
  `FROZEN` (T-05 §6.4) for both suites; `ThresholdsChanged` refuses a moved threshold; every
  per-case grader must have a seeded failing case. `calibration` is 1 − ECE (ECE ≤ 0.10).
- `evals/tax_account_mapper/suite.yaml` (39 cases: Ridgeline's 28 accounts as TXP-02 draws them,
  3 ambiguous abstentions, 3 adversarial: injected name, formula, homoglyph; 5 seeded) and
  `evals/tax_agreement_reader/suite.yaml` (12 cases: Ridgeline §706(d) straight percentage,
  Harborview waterfall, silent and conflicting conventions, an instruction inside the LPA; 7
  seeded). Generator kept in the session scratchpad; the YAML is the record.
- Dispatch: `python -m abacus_tools.evals --agent tax_account_mapper|tax_agreement_reader`;
  `make evals-entity-fast`.
- Test: `backend/tests/unit/tools/evals/test_t05t18_entity_suites.py`.
- No capability, prompt or spec: `tax.account_mapper` is T-05-T23 and the reader T-05-T36 (S38+).
- Rollback: revert.

## Partial
- Expert labels are AY's from the handoff's chart; the tax CPA's sign-off is a human step
  (`label_status: pending_cpa`).
- Harborview's and Ashford's charts are not in the handoff seed, so the mapper cases cover
  Ridgeline's chart plus synthetic ambiguous and adversarial accounts.
- `evals/baselines.yaml` cost rows come with the first real runs (T-05-T47).

## Progress log
- `2026-11-12` — Built (S37). Both suites run once on the fake outputs: passed, every seeded
  failure caught, calibration 0.946667. Unit tests written, run at the end pass.
