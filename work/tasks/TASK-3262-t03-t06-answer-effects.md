---
id: TASK-3262
title: T-03-T06 answer-effects engine (code rules, idempotent consumer, fail-closed slot, request handler)
spec: SPEC-643
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T06
branch: s27-t03-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Claire's Q2 and Q5 answers produce exactly one review point and one request each on replay,
attributed to the organizer rule and never to the agent, and a missing notices handler leaves the
upload in the binder."

## Plan (amber)
- `requests/events.py`: `QuestionnaireAnswered` (identifiers only), emitted by the portal answer
  write in its unit of work.
- `requests/answer_effects.py`: code evaluation (`show_when`, `when_equals`), `on_answered`
  (outbox, at-least-once: skip a recorded (answer, rule); call the slot's handler; one insert-only
  `answer_effects` row with the target, or `pending_handler`), `effect_log` read model;
  `SUBSCRIPTIONS` merged into `requests.api`.
- `requests/answer_effect_handlers.py`: `create_request_item` through P-06's insert, created by
  the system with the template publisher as named creator.
- Tests: `tests/unit/requests/test_t03t06_answer_effects.py`.
- Partial (recorded): `raise_review_point` and `flag_internal_review` need a system-actor issue
  path in C3 (they record `pending_handler` until C3 registers them); staff-edit-triggered
  effects are listed by T-03-T05's dry run and fired by the next T-03 batch.

## Progress log
- 2026-11-04: built. `answer_effects` is insert-only with a CHECK that an answerless row is a
  person's, so the target is written on the one row, after the handler.

## Decisions made during this task
DEC-2242.
