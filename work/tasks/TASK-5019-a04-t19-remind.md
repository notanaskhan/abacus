---
id: TASK-5019
title: A-04-T19 remainder - Remind as a follow-up draft
spec: SPEC-620
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T19
branch: s25c-a04-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s25c
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5019 · A-04-T19: Remind

TASK-3005 left `attention_flag_remind_route` at 501, waiting for a follow-up draft API. P-06-T14's
`draft_follow_ups` (C5 §12) has since landed, so nothing blocks it.

## Objective
AC2.3: "Remind… creates a follow-up **draft** to Dana; the flag's history records each conversion."

## Plan (amber)
- `workpapers/flags.py`: `remind`; `_open_flag` shared with `convert`; `NothingToRemind`.
- `workpapers/contract.py`: the route is live, behind `workpapers.core` and `binders.engine`.
- AUD-05: Remind… calls the route and says what happened; the placeholder that opened SHL-14 goes.
- No migration: 0581's `attention_flag_events` already holds the `reminded` event. Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Open requests only; the flag stays open; history records it | `tests/unit/workpapers/test_a04t19_remind.py` |
| A person only | `test_only_a_person_reminds` |
| Stored under the session's actor; 409 and 404 | `tests/integration/test_a04t19_remind_db.py` |
| Both flags | `test_a04_stub.py::test_a04t19_remind_needs_both_flags_and_reaches_the_service` |
| The screen | `AUD-05.test.tsx` c |

## Decisions made during this task
DEC-2381.

## Progress log
- 2026-11-06: built. Security self-review finding fixed: Remind also needs `attention_flag.convert`, because `client_service` holds only `follow_up.draft` and the route returns the flag's text. After that fix, targeted tests (1,282 backend, 8 web), tsc, eslint and check-fast all passed.
