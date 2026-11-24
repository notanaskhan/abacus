---
id: TASK-8908
title: "K-03-T14: Eval suite skeleton for workpapers.column_filler"
spec: SPEC-721
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-k03t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: K-03-T14
---

## Objective
suite.yaml with thresholds frozen (protected), case schema, graders for options, citations, first-person reason and exception recall, 40 SURL seed cases. Acceptance: suite.yaml with exception recall >= 0.97, accuracy >= 0.90, needs-input recall >= 0.95 and options, citations and reason at 1.0 merges before any column_filler prompt work starts.

## Done
- evals/column_filler/suite.yaml (protected; generated once by write_suite, then frozen): 75 cases (40 SURL seed rows 31/8/1, 11 further exceptions, 8 needs-input, 3 file + 3 firm-text adversarial, 10 seeded)
- abacus_tools/evals/column_filler.py: FROZEN thresholds (exception recall 0.97, accuracy 0.90, needs-input recall 0.95, output in options, two verified citations, first-person reason, file and firm-text containment, reserved actions absent, number provenance at 1.0), case schema, graders, run, naive baseline, generator (SURL rule from the invoice facts; seed from the Brightwater Hale scenario's SURL draw)
- python -m abacus_tools.evals --agent column_filler
- tests/unit/evals/test_k03t14_column_filler_suite.py (9 pass): thresholds frozen, changed threshold refused, 40 seed rows foot, every label follows the rule, ≥12 exceptions, seeded caught, naive fails, adversarial kinds, no prompt yet

## Progress log
- `2026-11-23` — Built in the S53 sequential stack (DEC-5910). The kept-on-rerun row (integration) and the text-mode section (citation coverage, faithfulness judge) arrive with the capability (K-03-T34/T35); the three ≥120-row populations and the Bedrock cost baseline with K-03-T53.
