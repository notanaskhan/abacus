---
id: TASK-8432
title: "Q-04-T202: Aug 2028 flag-hygiene bundle"
spec: None
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: q04-t202-flag-hygiene
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: Q-04-T202
---

## Objective
Q-04-T202: every flag on at a tax or EBP firm (T-05, T-07, C-01, W-01, A-08, A-09) renewed past Oct 20, 2028; make flag-calendar shows no expiry inside Sep 1 to Oct 20, 2028.

## Plan (amber)
1. Run `make flag-calendar` on main + the S48 stack and record it.
2. `docs/plan/status/S48-flag-hygiene.md`: clauses, today's state, what waits for the Aug 24, 2028 train.

## Progress log
- `2026-11-17` — Recorded in the S48 sequential stack. 129 flags; none inside a release window; none within 21 days. Partial: the renewals themselves run in the Aug 24, 2028 train (a renewal cannot reach past Oct 20, 2028 from today under ADR-089). Gates and tests run once at the S48 end pass (build first, test last).
