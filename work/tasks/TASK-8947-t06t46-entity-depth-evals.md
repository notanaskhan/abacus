---
id: TASK-8947
title: "T-06-T46: Eval suites for the entity-depth modes"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-t06t46
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T46
---

## Objective
Eval suites (protected): sections in evals/tax_return_analyst for the four modes, evals/tb_mapping tax_lines section, decisions.recommender section_754 cases; synthetic and adversarial cases (instruction in an invoice, wrong-date bait, hostile account names).

## Done
- abacus_tools/evals/tax_entity_depth.py: graders, FROZEN thresholds, load/run/gate
- evals/tax_return_analyst/suite.yaml: 4 modes, 3 attacks, no-consent case, 5 seeded
- evals/tb_mapping/suite.yaml sections.tax_lines: 6 pass/adversarial + 5 seeded
- evals/tax_recommender_modes: 3 section_754 pass cases + wrong-date-bait seeded
- CLI --agent tax_return_analyst|tb_mapping_tax_lines
- tests/unit/evals/test_t06t46_entity_depth.py (4)

## Progress log
- `2026-11-23` — 2026-11-23: all three suites pass their gates on the fake model; tb_mapping's A-09 loader unaffected. Human remainder: notanaskhan approves the thresholds; the tax CPA signs labels. Eval-suite registry regen in the end pass.
