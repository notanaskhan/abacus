---
id: TASK-6823
title: "A-07-T51 (partial): the M16 runbook docs/runbooks/audit-release-archive.md; rehearsal, shadow, drill and approvals wait for staging"
spec: SPEC-644
acceptance_criteria: [AC-DOD-7, AC-DOD-9]
risk_zone: red
status: in-review
branch: s36-a07-t51
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T51
---

## Objective (row)
The runbook is rehearsed on staging, and the flip request carries passing journeys, shadow
evidence, the delta-test closure and both approvals.

## Built
`docs/runbooks/audit-release-archive.md` covers:
- release failure;
- a stuck lock;
- a seal mismatch (RB-29);
- post-lock additions;
- rollback;
- the shadow;
- the restore drill;
- the flip checklist.

Every workflow id, audit action, flag and function name is checked against the code. README row
added; DEC-3415 records the decision.

## Partial (cannot be done here)
- The staging rehearsal, the shadow from Mon Mar 6, 2028, the restore drill and both founders'
  approvals. Staging is not up, and the approvals are the founders'.
- The A-07-T46 delta security test is deferred under DEC-1389 and stated as such.

## Progress log
- `2026-11-11` — Runbook written (S36). Not rehearsed.
