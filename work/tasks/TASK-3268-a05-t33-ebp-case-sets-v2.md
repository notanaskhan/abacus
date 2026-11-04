---
id: TASK-3268
title: A-05-T33 EBP case sets v2 (ebp_reconcile, ebp_trust, ebp_form5500, related_parties)
spec: SPEC-000  # row (SPEC-640 AC-33)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T33
branch: s27-a05-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Every EBP mode has frozen thresholds and adversarial cases before its prompt merges."

## Plan (red)
- `evals/workpapers_section_drafter/suite.yaml` (PROTECTED): the four modes join; key cases for
  each (Northwind register totals, Harborline net trust assets, the draft Form 5500's Part IV,
  parties in interest) and an instruction-in-file trust report; `forbidden_absent` = 1.0 on the
  four modes; Part IV inconsistencies gated by `seeded_exception_recall` ≥ 0.97.
- `abacus_tools/evals/section_drafting.py`: `EBP_V2_MODES`, the `forbidden_absent` metric over
  `labels.forbidden` (normalised), recall extended to `ebp_form5500`.
- `_eval_suites.py` regenerated. Tests: `tests/unit/evals/test_a05t33_ebp_case_sets_v2.py`.

## Progress log
- 2026-11-04: built; the fake answers pass every grader (a dated sentence in the Part IV row was
  rewritten so number provenance holds).

## Decisions made during this task
DEC-2248.
