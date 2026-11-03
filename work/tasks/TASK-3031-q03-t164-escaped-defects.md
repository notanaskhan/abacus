---
id: TASK-3031
title: Q-03-T164 escaped-defect fix-forward, 2027 Q3 part 1
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # every escaped defect of the period has a fix and a recurrence test, and the log names the layer that missed it
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T164
branch: s25-q03-t164
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Every escaped defect of the period has a fix and a recurrence test, and the log names the layer
that missed it." The period is the S25 batch: what its CI runs and end review found after the rows
had passed their own checks.

## Plan (red)
- ED-300: `kernel/error_tracking.py` keeps exact trace and span ids out of the TIN mask.
- ED-301: `abacus_tools/harness/mailbox.py` reads a sign-in code only as a whole token.
- ED-302: CAST-001 in `abacus_tools/quality/banned_patterns.py`: `cast(AuthContext, ...)` carries a
  reason on its line; the 14 existing casts state theirs (each is a person: an isinstance check
  or HOME-01's count slot).
- `docs/quality/escaped-defects.md`: ED-300 to ED-316 with the layer that should have caught each.
- Rollback: revert. No migration, no flag.

## Acceptance
| Defect | Recurrence |
|---|---|
| ED-300 | `test_ed300_*` in `tests/unit/kernel/test_error_tracking.py` |
| ED-301 | `tests/unit/tools/test_q03t164_mailbox_code.py` |
| ED-302 | CAST-001 cases in `tests/unit/quality/test_banned_patterns.py` |
| ED-303 to ED-316 | fixed by DEC-2077, DEC-2078 and TASK-2928, each with the test named in its row |

## Progress log
- 2026-11-03: built. error tracking 68 passed; mailbox and fakes 19 passed; banned patterns 3,251
  passed and the repo is clean under CAST-001.

## Decisions made during this task
DEC-2079.
