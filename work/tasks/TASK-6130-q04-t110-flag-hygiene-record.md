---
id: TASK-6130
title: "Q-04-T110 Dec 14-17 bundle record: A-06, N-04, T-03 retirements and the flag calendar"
spec: SPEC-000  # row (Q-04-T110)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: Q-04
plan_key: Q-04-T110
branch: s30-q04-t110
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Dec 14-17 bundle and Dec 16 train: renewals to expiries after Apr 20, 2028 (A-05, T-01, P-04), A-06 flags retired into assurance_completion, N-04 and T-03 flags retired; make flag-calendar shows no expiry Jan 1-Apr 20.

## Plan
- `docs/plan/status/S30-flag-hygiene.md`: each clause with where it landed (A-06-T37 #1435; N-04-T27 #1384; T-03-T18 #1387), why the 2027 renewals cannot be written in 2026 (DEC-137 180-day limit), and the flag calendar snapshot (78 flags, none in a window).

## Progress log
- 2026-11-08: built. `python -m abacus_tools.codegen.feature_flags --calendar` run: 78 flags, 0 within 21 days, none in a window.

## Decisions made during this task
None.
