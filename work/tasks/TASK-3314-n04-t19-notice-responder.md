---
id: TASK-3314
title: N-04-T19 notices.responder capability v1 (analyze and extract)
spec: SPEC-000  # row (N-04-T19)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T19
branch: s28-n04-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"On synthetic tenants the Whitley analysis shows a cited explanation and Agree recommended, a joint return with one consent is refused with consent_7216, and a narrative with an unsupported number is never shown."

## Plan
- `agents/specs/notices.responder.yaml` (modes analyze and extract), prompts `notices.analyze@v1` and `notices.extract@v1`, closed outputs in `handoff.py`, fake responses.
- `agents/notice_responder.py`: gates, one gateway call, code's checks, run records.
- `notices/agent_step.py`: the registered hook; `analysis.run` passes code's rows.
- `_specs.py` and `_eval_suites.py` regenerate at the end pass.
- Rollback: flag `notices.responder` off.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2313
