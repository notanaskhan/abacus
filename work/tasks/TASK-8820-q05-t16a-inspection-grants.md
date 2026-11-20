---
id: TASK-8820
title: "Q-05-T16: Inspector access (part 1 of 2): identity inspection_access_grants"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q05t16a
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T16
---

## Objective
Thomas Whitcombe reads Bayside's archive and activity read-only during INS-26-02 and loses access at conclusion, a walled inspector sees nothing, and only Margaret Okonkwo can decide the evaluation card.

## Done
- Migration 0995 inspection_access_grants (identity, forced RLS, insert-only but revocation)
- identity/inspection_grants.py: issue (in the planner's unit of work), revoke_for_inspection (conclusion), sweep (expired, hourly in the access-end pass), INSPECTION_READS read-only set, expiry = conclusion or due + 30 days
- authorise: an inspector relationship for an INSPECTION_READS action under a live grant, after walls; visible(): the grant's engagements OR-ed in (walls still applied)
- registry; reviewed audit actions; unit tests

## Progress log
- `2026-11-20` — Plan (red, authz core): table, service, two authz hooks, sweep; rollback revert + downgrade 0995. Part 2 (firm-scope decision cards) is the next PR. Generated allow/deny tests and the security review at the end pass.
