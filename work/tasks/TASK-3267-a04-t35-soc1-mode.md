---
id: TASK-3267
title: A-04-T35 mode soc1 (SOC 1 reader and CUEC mapper) on the section drafter, spec v10
spec: SPEC-000  # row (SPEC-620 AC7.6)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T35
branch: s27-a04-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
Mode `soc1`: the SOC 1 report's period, opinion, objectives, subservice carve-outs, exceptions
with a proposed impact and CUECs with page references, as cited suggestions; CUEC-to-control
mapping suggestions; never reliance, never a computed gap.

## Plan (red)
- Prompt `workpapers.section_draft.soc1@v1` (the untrusted-block rule, reserved words, no gap).
- `assurance/soc1_mode.py`: the mapping (SOC report pages through `documents_for_areas`, the
  team's control activities as facts), registered in `assurance/api.py`.
- Spec `workpapers.section_drafter` v10: soc1 on its own prompt; `_specs.py` and
  `_eval_suites.py` regenerated (the latter also carries A-04-T33's suite change).
- Tests: `tests/unit/assurance/test_a04t35_soc1_mode.py`; the A-04-T33 suite grades it.

## Progress log
- 2026-11-04: built. The plan year is not a model input: the agent context cannot read the
  engagement's metadata, and the gap is code's after a person adopts the period.

## Decisions made during this task
DEC-2247.
