---
id: TASK-7316
title: "P-05-T16: Rollout and docs: RB-01 flag-flip and rollback section, final contract doc, CL-1 consolidation ticket, flag renewal calendar, canary flip in the Tue Mar 28 window"
spec: SPEC-650
acceptance_criteria: [AC-DOD-2, AC-DOD-9]
risk_zone: green
status: in-progress
branch: s37-p05-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-05-T16
---

## Objective
Both flags are on for the canary tenant after a Tuesday-window flip approved by both founders,
rollback is rehearsed on staging, and CL-1 and the Apr 13 flag renewal are filed.

## Built
- `docs/runbooks/RB-01-deploy-and-rollback.md`: the P-05 section (what each flag turns on, the
  order, the gates before the flip, the rollback that deletes nothing, the staging rehearsal steps,
  the follow-ups).
- `docs/contracts/collaboration.md`: status final (DEC-4315).

## Follow-ups (filed here; not GitHub issues)
- **CL-1:** consolidate the legacy SPEC-032 comments into P-05 threads (P-05 §2.3), after every
  firm has `collaboration.v2` on.
- **Flag renewal, Apr 13, 2028:** `collaboration.v2` and `audit_trail.engagement_activity`, in
  RB-26's wave.

## Partial (status in-progress)
- The canary flip (Tue Mar 28, 2028, both founders' approval) and the staging rollback rehearsal
  are ops steps: no staging or production in this build. The rehearsal goes in RB-01's log.

## Progress log
- `2026-11-12` — Docs built (S37); the flip and rehearsal wait for staging.
