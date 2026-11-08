---
id: TASK-6219
title: A-07-T21 independent AC tests for A-07-T15, T18, T19 and T23's guard
spec: SPEC-644
acceptance_criteria: [AC-1]  # fails if the EQR can sign L1-L4 or if G6 reads met before a concurrence row exists
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T21
branch: s31-a07-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (red: written before building)
- Tests (ADR-078, from the row, SQMS 2 and A-07 F1/F9): `tests/unit/assurance/test_a07t21_completion_independent.py`. It covers:
  - the I-GATES G6–G9 table by engagement type and release mode;
  - the EQR signs L5 only and is denied every mutating workpaper act;
  - a non-EQR or agent concur is 403 `eqr_only`;
  - the EP never opens as the EQR;
  - the digest is built from decided cards only;
  - the A-07 registrations are inert with the flags off;
  - the bring-down never starts dark or external.
- Fix surfaced by the suite (DEC-2817): `gates.in_app_g6` stays unmet while an EQR is on the team with no concurred review (new `_eqr_on_team`). Two existing gate tests stub `_eqr_on_team` (no EQR on the team) so their cases keep reaching the same answers; no assertion changed.
- Rollback: revert `gates.py` and the two stubs; delete the new file.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2817 | G6 unmet before a concurrence when an EQR is assigned but no review opened | no |

## Progress log
- 2026-11-08: written; the G6 gap was found while writing the suite and fixed here. Runs at the S31 end pass.
