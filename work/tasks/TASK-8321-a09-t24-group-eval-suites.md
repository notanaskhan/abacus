---
id: TASK-8321
title: "A-09-T24: Eval suites (protected): tb_mapping and elimination_proposal v1"
spec: SPEC-658
acceptance_criteria: [AC-1, AC-3]
risk_zone: red
status: in-review
branch: a09-t24-group-eval-suites
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T24
---

## Objective
Spec section: docs/plan/epics/A-09.md §6.
Eval suites (protected): tb_mapping and elimination_proposal v1.

## Plan (red)
1. `evals/tb_mapping/suite.yaml` v1 (protected thresholds): Harlow & Pike accounts by code and name, the 1460/2215 intercompany pair, adversarial account names (abstain), a seeded wrong caption; labels `pending_practitioner`.
2. `evals/elimination_proposal/suite.yaml` v1 (protected thresholds and weights): E1a to E5, 20 synthetic groups, an instruction in a cell, a seeded unbalanced proposal; dangerous errors weigh 3.
3. `abacus_tools/evals/group_audit.py`: FROZEN thresholds and weights, loaders that refuse a change, code graders on recorded responses, seeded-failure checks, `main`.
4. Tests: `tests/unit/evals/test_a09t24_group_suites.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5316). The unit file ran green (2 tests: both suites meet their thresholds on the recorded responses; every seeded defect fails its grader). Partial: the full 244-account chart, the ECE calibration grader and the group cases for decisions.recommender and the component cases for communications.drafter wait on a practitioner's labels (human). Gates and
  tests run once at the S47 end pass (build first, test last).
