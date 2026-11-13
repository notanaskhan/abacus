---
id: TASK-7706
title: T-05-T49 decisions.recommender modes convention_706d and section_754
plan_key: T-05-T49
spec: SPEC-651
acceptance_criteria: [AC-10.1, AC-10.2]  # T-05 F10
risk_zone: red
status: in-review
branch: t05-t49-recommender-modes
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Two recommender modes whose options come from code, whose recommendation stays inside the allowed
set with a cited reason, in a single call; a person decides.

## Plan (red)
- Files: `agents/recommender_modes.py`, `agents/api.py` exports, `tax/recommendation_facts.py`,
  prompts `decisions.recommend.convention_706d/v1.txt`, `decisions.recommend.section_754/v1.txt`.
- No migration, matrix or flag. The materiality recommender (PROTECTED) is unchanged.
- Tests: `backend/tests/unit/tax/test_t05t49_recommender_modes.py`; the fake-model suite
  `evals/tax_recommender_modes` (T-05-T30) in the end pass.
- Rollback: revert; nothing calls the modes until T-05-T52.

## Partial
- No caller yet: T-05-T52 raises the §754 card (reserved to the engagement partner) and the
  convention question's HOME card with the recommendation; the run question's recommended option
  stays code's (DEC-4704) until then.
- The fake model's responder for the two prompts and the suite registration are T-05-T47's
  bundle; real-model runs are T-05-T64.

## Progress log
- 2026-11-13: built; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4709 | the modes' module, checks and facts | no |
