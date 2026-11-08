---
id: TASK-6113
title: "A-05-T56 mode related_parties: its own prompt and mapping, no person's name, no conclusion (spec v13)"
spec: SPEC-000  # row (A-05-T56)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T56
branch: s30-a05-t56
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-05 F11: match vendor and customer masters against owners, directors, officers and employee addresses from the minutes and the HR roster; candidates with evidence; the director's name never surfaced; never concludes.

## Plan
- Prompt `workpapers.section_draft.related_parties@v1`: candidates with what matched and where it is shown, people by role and document only, quotes with names replaced by role, no counting, no conclusion, "management should confirm".
- Spec v13; `_specs.py` and `_eval_suites.py` regenerated.
- `assurance/related_parties_mode.py`: mapping (masters, minutes, roster areas; no facts); registered in `assurance/api.py`.
- Eval case `granite_peak_related_parties_peakline` (Peakline proposed with the Feb 12, 2026 minutes reference; the director's name and any conclusion forbidden).
- Test: `tests/unit/assurance/test_a05t56_related_parties_mode.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2711
