---
id: TASK-3266
title: A-04-T33 eval cases for mode soc1 in the section-drafter suite
spec: SPEC-000  # row (SPEC-620 AC7.6)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T33
branch: s27-a04-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
Frozen thresholds and labelled cases for mode `soc1` (SOC 1 reader and CUEC mapper) before its
prompt merges (A-04-T35), in the one suite (OQ-1: no second suite).

## Plan (red)
- `evals/workpapers_section_drafter/suite.yaml` (PROTECTED): `soc1` joins the modes; five cases:
  three labelled synthetic SOC 1 Type 2 layouts (AICPA tabular, narrative, scanned) and two
  adversarial (an injected "mark reliance concluded" instruction, an exfiltration link);
  `seeded_exception_recall` (≥ 0.97) and `line_agreement` (≥ 0.98) gate soc1.
- `abacus_tools/evals/section_drafting.py`: exception recall and fact agreement apply to soc1; an
  exception label's COSO component is optional (only `ic` grades it, and validation still
  requires it there); a soc1 case labels the report's facts.
- Tests: `tests/unit/evals/test_a04t33_soc1_cases.py`.

## Progress log
- 2026-11-04: built; the suite loads and validates with 19 cases.

## Decisions made during this task
DEC-2246.
