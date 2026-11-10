---
id: TASK-3312
title: "N-04-T16 response part 2: send for signature, readiness, mark sent, replies and timers"
spec: SPEC-000  # row (N-04-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T16
branch: s28-n04-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"On staging the Whitley response reaches Ready to send only after both signatures and an accepted confirmation, mark-sent on Sep 17 schedules Nov 16, and no route ever calls an irs.gov host."

## Plan
- `notices/sending.py`: C11 kind, C7 source, send for signature, readiness, envelope consumer, mark sent, agency reply.
- `notices/response_workflow.py` + types + activities + `notices/events.py`.
- `DocumentKind.tenant_variables_provider` (the S27 partial's blocker).
- `kernel.dispatch.signal_workflow`.
- Routes live: send-for-signature, mark-sent, agency-replies.
- Replay history at the end pass.
- Rollback: routes to 501.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2311
