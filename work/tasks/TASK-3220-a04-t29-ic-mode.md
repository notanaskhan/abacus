---
id: TASK-3220
title: A-04-T29 mode ic (Exceptions rows; code's PM and CT comparison)
spec: SPEC-620
acceptance_criteria: [AC-23, AC-21]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T29
branch: s26-a04-t29 (stacked on s26-a05-t27)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"On the fake model the Northwind run writes 7 rows (1 SD, 3 Deficiency, 3 Exception for
resolution) with verified citations, row 3's 48,600 is compared by code to 189,150 and 12,610,
and R3 gets a v2 rationale suggestion."

## Plan (red)
- Prompt `workpapers.section_draft.ic@v1`; spec v9.
- `assurance/ic_mode.py`:
  - `compare` and the narration (code; AC6.5);
  - `comparison_facts`;
  - `ic_inputs` (control evidence plus code's PM and CT).
- Mapping registered; `_specs.py` and `_eval_suites.py` regenerated.
- Test: `tests/unit/assurance/test_a04t29_ic_mode.py`.

## Progress log
- 2026-11-03: built. Partial:
  - the outbox re-draft consumer (`workpaper.version_created` on an agent-written Internal
    Control version → `risk` runs for linked risks). Starting a run needs the IC run's initiator
    as a person context, and the event names no actor yet; AUD-08's manual "Draft with agent" is
    the plan's own fallback (§1 item 3).
  - Pack validation before the model call stays the drafter's existing check (AC6.1, A-04-T11).
  - The fake-model Northwind run is the A-04-T30 suite's.
  Tests at the S26 end review.

## Decisions made during this task
DEC-2220.
