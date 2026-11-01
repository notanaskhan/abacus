---
id: TASK-2921
title: K-01-T22 eval suite evals/methodology_import
spec: SPEC-600
acceptance_criteria: [K-01 §6]
risk_zone: red
status: in-review
epic: K-01
plan_key: K-01-T22
branch: s24-k01-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

The importer's protected suite with K-01 §6's thresholds, graded by code on the fake model.

## Acceptance (backlog)

The suite runs in CI on the fake model and meets every section 6 threshold on one budgeted Bedrock run recorded against the cost baseline.

## Plan

- `evals/methodology_import/suite.yaml`: single-column (BH EBP v3 style with a multi-page step), two-column and table-heavy layouts, an adversarial file (instruction, white text, "approve this version"); thresholds as K-01 §6 (recall, precision, assignment ≥ 0.98; fidelity ≥ 0.95; numeric fidelity and citation verification 1.0; hard-case flag recall ≥ 0.95; false flags ≤ 0.10; containment 1.0).
- `abacus_tools/evals/methodology_import.py`: graders over `ImportBatchOutput`, `run`, `import_suite_main` (fake only); CLI `--agent methodology.importer`; `agents.api` exports the import output models; the spec test's owed list drops the suite.
- Tests: `tests/unit/tools/test_k01t22_methodology_import.py` (fake answers pass; negative controls fail).
- **Human to-do (DEC-1967):** the one budgeted Bedrock run with the evaluation key, recorded in `evals/baselines.yaml`; calibration (ECE) is reported from that run.

## Progress log

- 2026-11-01: built in abacus-s24. The fake answers were checked once against the graders while writing; tests not run.
