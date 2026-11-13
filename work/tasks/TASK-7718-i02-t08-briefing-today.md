---
id: TASK-7718
title: I-02-T08 Capability briefing.today v1 (spec, prompt, EngagementBriefing, validator, briefing step)
plan_key: I-02-T08
spec: SPEC-654
acceptance_criteria: [AC-3, AC-10]
risk_zone: red
status: in-review
branch: i02-t08-briefing-today
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
One engagement's Today briefing written by the model from code's facts, validated by code with
one repair, stored in `daily_briefings` by a run step.

## Plan (red)
- `agents/specs/v2/briefing.today.yaml` + `_specs_v2.py`; prompt; `agents/briefing/today.py`;
  `agents/api.py` registers the step; `_eval_suites.py` regenerated.
- Tests: `backend/tests/unit/briefing/test_i02t08_briefing_today.py`; the suite (I-02-T09) runs
  on the fake model in the end pass.
- Rollback: revert; no build route starts the step until I-02-T13.

## Partial
- Citations: candidates are refs, not C4 citation rows; lines carry fact references (DEC-4721).
- Titles and recommendations passed to the step are empty until I-02-T10/T13 supply them from
  the C13 presenters; the step's replay from committed history is P-10's runtime (not re-tested).
- The user-scope snapshot row (counts, lead facts, card refs) is I-02-T10's.

## Progress log
- 2026-11-13: built; spec compiled; step registered; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4721 | capability, validator, repair and step | no |
