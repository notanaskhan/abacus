---
id: TASK-7937
title: "I-02-T14: Today questions (POST /v1/me/today/questions on a firm-level Today session, read only)"
plan_key: I-02-T14
spec: SPEC-654  # I-02 §3.7, §6.2
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
branch: i02-t14-today-questions
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
Asking about the day returns a cited read-only answer; "Approve the four sign-offs" gets a refusal
pointing to SHL-12 with no proposal row written.

## Plan (red)
- `workbench/today_questions.py` (new): availability first (`agents.api.firm_capability_blocked`),
  the brief's question context (`practice.api.question_context`), the per-day Today session with
  its `context_added` item, `post_message`, audit `today_brief.question_asked` (ids only).
- `workbench/today_questions_contract.py`: the route goes live (no 501).
- `workbench/sessions.py`: a Today session's message opens a firm-level turn run.
- `workbench/session_turn_v2.py`: a Today turn never plans; `plans_off` there becomes the
  `today_read_only` notice.
- `agents/session_turns.py`: `open_turn_run(engagement_id=None)`, `turn_capability_ready` for a
  firm-level run, `firm_capability_blocked`; exported from `agents.api`.
- `practice/today/assembly.py`: `question_lines`, `question_context` (exported from
  `practice.api`). Audit fallback list: `today_brief.question_asked`.
- Tests: `backend/tests/unit/workbench/test_i02t14_today_questions.py`.
- Rollback: revert the PR (the route returns to 501); Today sessions written stay as sessions.

## Partial
- The ten Today ask cases for `evals/workbench_assistant` (I-02 §6.3) are not added here: that
  suite is frozen with W-02's thresholds; they join with I-02-T20's eval runs.
- The firm-level turn's engagement-scoped tools refuse (a firm-level run holds firm actions only);
  answers rest on the brief context and the briefings' verified citations.

## Progress log
- 2026-11-14: built; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4932 | firm-level Today session and turn; code context; never plans; availability first | no |
