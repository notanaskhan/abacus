---
id: TASK-7958
title: "P-03 reveal window: whole seconds from the server's revealed_at"
plan_key: P-03-T18
spec: SPEC-000  # row: follow-up from the S43 tip CI (a P-03-T18 flake)
acceptance_criteria: [AC-1]  # a 30 s reveal's expires_at - revealed_at is exactly 30 s
risk_zone: red
status: in-review
branch: p03-reveal-one-clock
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-15
updated: 2026-11-15
---

# P-03 reveal window

## Plan
- Cause: `pii_reveals.revealed_at` is the column default `clock_timestamp()`, and `expires_at`
  is the app's `clock_timestamp() + :expires`. Two clock reads in one INSERT can be 1 µs apart,
  and `test_ac26_samuel_reveals_the_ssn_once_logged_without_the_value` asserts exactly 30 s.
- Not the app: the app role has no INSERT grant on `revealed_at` (0109's `insert_columns`), by
  design, so the server alone stamps it and a reveal cannot be backdated.
- Fix: migration 0884 on 0883 adds a BEFORE INSERT trigger. It rounds `expires_at - revealed_at`
  to whole seconds from `NEW.revealed_at`. No app change, and no new grant.
- Rollback: downgrade drops the trigger and its function.
- Tests: the reveal integration files (trust_kit reveal, A-05-T18, A-05-T29, P-03-T21, G-02-T09,
  P-03-T18), the schema check, and the migration round trip.

## Progress log
- 2026-11-15: a first attempt (INSERT … SELECT setting `revealed_at`) failed with 17 errors on
  the column grant. Reverted; the trigger is the fix.
