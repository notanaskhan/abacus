---
id: TASK-8717
title: "Q-05-T10: Eval suite evals/post_issuance_analysis, frozen before any prompt"
spec: SPEC-711
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18]
risk_zone: red
status: in-review
branch: q05-t10-pi-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T10
---

## Objective
30 labelled synthetic cases (10 below and 6 above clearly trivial, 4 disclosure-affected, 4 omitted procedure, 6 instruction-in-file certifications), the Northwind PI-01 golden case and one seeded case per grader, with seven graders all at 1.0 frozen in suite.yaml (number provenance, citation verification and coverage, the not-decided sentence, reserved actions absent, recommendation consistency, adversarial containment). The loader refuses changed thresholds; a fake-model baseline fails every class.

## Plan (red)
1. abacus_tools/evals/post_issuance_analysis.py (FROZEN, loader, graders, run, naive_baseline, main); registered in the evals CLI.
2. evals/post_issuance_analysis/suite.yaml (generated once from the scratch generator, then frozen).
3. tests/unit/evals/test_q05t10_post_issuance_suite.py.

## Progress log
- `2026-11-19` — Built; tests pass (5). Labels pending the audit CPA (pending_cpa). The real-route (Bedrock) run and cost baselines come with the capability's prompt task. Gates and tests run once at the S51 end pass (build first, test last).
