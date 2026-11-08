---
id: TASK-6112
title: "A-05-T55 mode ebp_form5500: its own prompt and mapping, code's differences as facts (spec v12)"
spec: SPEC-000  # row (A-05-T55)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T55
branch: s30-a05-t55
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-05 F9: the mode reads draft Schedule H and Part IV fields with citations (P-11 word layer, OCR when scanned), proposes documented basis differences as reconciling items, and drafts Note 8 and the 4i/4a rows; it never records.

## Plan
- Prompt `workpapers.section_draft.ebp_form5500@v1`: copy amounts as printed, never total or compare, propose basis differences citing their documents, flag a Part IV disagreement for the team, classify nothing.
- Spec `workpapers.section_drafter` v12: the mode's own prompt; `_specs.py` and `_eval_suites.py` regenerated.
- `assurance/ebp_form5500_mode.py`: mapping (form 5500, Schedule H, Part IV and contributions documents; facts `diff.<line>` from code's tie-out and `late_deposits_4a`); registered in `assurance/api.py`.
- Tests: `tests/unit/assurance/test_a05t55_form5500_mode.py`; three older mode tests read the spec version as at least 11.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2710
