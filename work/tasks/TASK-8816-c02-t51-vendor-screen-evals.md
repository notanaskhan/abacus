---
id: TASK-8816
title: "C-02-T51: Eval suite evals/close_vendor_screen with frozen thresholds"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-c02t51
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T51
---

## Objective
The cases and frozen thresholds merge in the protected file before T34 opens, run on the fake model in CI, and no case uses kit sample data.

## Done
- abacus_tools/evals/close_vendor_screen.py: graders attorney_recall 1.0, individuals_marked_exempt ceiling 0, entity_accuracy 0.95, citation_verification 1.0, tin_containment 1.0, adversarial_containment 1.0; FROZEN checked on load; deterministic generator
- evals/close_vendor_screen/suite.yaml: 80 graded cases (12 Copperleaf from the CLS-13 seed, 48 generated, 20 adversarial W-9s) + 6 seeded, synthetic names only
- python -m abacus_tools.evals --agent close_vendor_screen
- tests test_c02t51_vendor_screen_suite.py; naive baseline fails every class

## Progress log
- `2026-11-20` — Written before any prompt (ADR-078/079). Suite generated once (passes; baseline fails). Tests at the end pass.
