---
id: TASK-3022
title: A-05-T16 EBP-02 provisions service
spec: SPEC-640
acceptance_criteria: [AC-14]
risk_zone: amber
status: done
epic: A-05
plan_key: A-05-T16
branch: s25-a05-t16 (stacked on s25-a05-t19)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Sign off answers 409 provisions_unverified until all 20 ticks exist, and EBP-03 reads the entry
rule from the verified provision, never from the draft."

## Plan (amber)
- Migration 0653 (on 0652): `ebp_plan_reviews`, insert-only, person only. Rollback: drop it
  (expand only, nothing reads it but this service).
- `assurance/ebp_provisions.py`: start (records the review, starts the `ebp_provisions` run on
  EBP-02), the mode mapping (documents D1 to D3), the read model, the sign-off guard,
  `verified_provisions`.
- `workpapers/guards.py` (`register_sign_off_guard`), `ReviewableFacts.blocked_code` and
  `review.sign_offs.SignOffBlocked` (409 `sign_off_blocked`).
- `review.field_states`: several fields' current values and current ticks.
- Routes served: GET current, POST plan-reviews.
- Tests: `tests/unit/assurance/test_a05t16_provisions.py` (9).

## Progress log
- 2026-11-02: built; unit tests pass. The SPD conflict and amendment tag on the read model wait
  for the SPD values a person enters (DEC-2069). A-05-T20's engine still reads its defaults; the
  wiring to `verified_provisions` is one call in the eligibility service when it is built.

## Decisions made during this task
DEC-2069.
