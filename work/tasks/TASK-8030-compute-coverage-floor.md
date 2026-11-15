---
id: TASK-8030
title: "The compute coverage floor back at 100% line and branch"
spec: SPEC-000  # quality floor
acceptance_criteria: [AC-1]  # stage 2's coverage floor holds compute at 100 / 100
risk_zone: amber
status: in-review
branch: compute-coverage-floor
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-15
updated: 2026-11-15
plan_key: Q-03
---

## Objective
`coverage-thresholds.yaml` holds `compute` (`src/abacus/*/compute/*.py`, 55 files) at 100% line and branch. Main CI has measured 98.1% / 93.1% since 61c47b52b. The floor is never lowered (AGENTS 13).

## Progress log
- `2026-11-15` — Measured locally the way CI does (the unit set under coverage). Gaps were in 11 files:
  - EBP eligibility;
  - reporting `fs_draft` and `tie_out`;
  - T-05's entity `allocation`, `schedule_k`, `tb_pipeline`, `ties` and `waterfall`;
  - the workbook `dag`, `formula` and `tieouts`.
- Tests: `tests/unit/assurance/test_compute_floor_eligibility.py`, `tests/unit/reporting/test_compute_floor_reporting.py`, `tests/unit/tax/test_compute_floor_entity.py`, `tests/unit/workpapers/test_compute_floor_workbook.py`. They cover every refusal, Schedule K's payments by partner and state cells, and every waterfall rung path, among others.
- Six formula-engine guards cannot be reached, because the tokenizer or reference reader refuses first or the regex always matches. Each is marked `# pragma: no cover` with its reason, as line 462 of the same file already was. The evaluator's two type guards are tested directly.
- Result: compute 99.97% line and 99.89% branch before the last `foot` case; after it, the remaining file reads 100%. check-fast passes in full.
- Also fixes three reds on main 9160f5095 (CI 43656694200):
  - the E501 in `test_f03_status_vocabulary.py` (#2011);
  - DB-001 in the J08 test, now through `Seeder` (#2004);
  - TASK-8026's acceptance IDs (#2004).
