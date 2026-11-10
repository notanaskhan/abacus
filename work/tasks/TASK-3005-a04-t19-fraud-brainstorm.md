---
id: TASK-3005
title: A-04-T19 AUD-05 narrative extras — fraud brainstorm, minutes gate, inquiries, flags
spec: SPEC-620
acceptance_criteria: [AC-12, AC-13, AC-14]
risk_zone: amber
status: done
epic: A-04
plan_key: A-04-T19
branch: s25-a04-t19 (stacked on s25-n04-t05 for the migration chain)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Margaret approves the minutes while Marcus gets 403, Escalate on the PBC GAP flag yields a draft
request nothing sends, and Dana's questionnaire stays Draft until Hannah sends it."

## Plan (amber)
- Migration 0651 (on 0650): `fraud_brainstorm_sessions.row_version`.
- `assurance/fraud_brainstorm.py`: session read and record (EQR refused), minutes (person or the
  `fraud_minutes` applier), EP approval (five layers), gate `fraud_minutes_approval`, inquiries.
- `workpapers/flags.py`: convert a PBC GAP flag (request draft or review note) with history.
- `requests.create_questionnaire(engagement_id=…)`; FRAUD-MINUTES-001; C16
  `fraud_minutes_awaiting_approval`; planning contract aligned with 0613 (DEC-2055).
- Rollback: revert; `alembic downgrade 0650`.

## Acceptance
| Check | Test |
|---|---|
| EP approves, senior 403; gate opens and closes | `test_a04t19_fraud_brainstorm.py::test_ac2_4_the_partner_*` |
| Stale hash 409; edit resets approval | `test_ac2_4_a_stale_hash_*` |
| EQR never an attendee; stale session 409 | `test_ac2_4_the_eqr_*`, `test_ac2_4_a_stale_session_*` |
| Inquiries are drafts / recorded | `test_ac2_5_*` |

## Progress log
- 2026-11-02: built. Remind (follow-up draft) stays 501: no person-authored follow-up draft API
  yet. Tests at the S25 end review.

## Decisions made during this task
DEC-2055.
