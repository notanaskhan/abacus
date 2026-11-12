---
id: TASK-7425
title: "P-10-T56: close-out: flag renewal calendar to the Tue Apr 25, 2028 train, capacity ledger and actuals, C6 and C17 register entries, hand-off notes"
spec: SPEC-647
acceptance_criteria: []
risk_zone: green
status: done
branch: s38-p10-t56
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T56
---

## Objective
No P-10 flag expires before its renewal, and the capacity ledger records P-10 actuals.

## Built
- `docs/plan/status/flag-renewals-2027.md`: the P-10 flags' calendar (due Thu Feb 25, 2027 on
  today's 2027-05-07 expiries; each train after; the Tue Apr 25, 2028 renewal to at most Mon Jul
  24, 2028, past M17; retirement and kill-switch conditions).
- `docs/architecture/feature-flags/agents.yaml`: the three flags name `j11-workbench` and
  `j23-audit-partner-morning` as their flip journeys.
- `docs/contracts/README.md`: C6 v2 frozen and live; C17 v1 live.
- `docs/product/capacity-ledger.md`: P-10 actuals (50 done 50.75 te, 7 partial 4.5, 1 deferred 0.5).
- `docs/plan/status/P-10-closeout.md`: what is left per row and the hand-off notes.
- `backend/tests/unit/tools/test_p10t56_closeout.py` (6 pass). DEC-4414.

## Progress log
- 2026-11-12: built; test passes. The renewals themselves happen on their trains (the 90-day rule
  forbids renewing to 2028 now).
