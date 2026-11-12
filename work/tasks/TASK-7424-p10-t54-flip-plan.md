---
id: TASK-7424
title: "P-10-T54: M17 flip plan: docs/runbooks/runtime-v2-flip.md (rollback is flags off; runs persist), shadow of engagement runs on staging and the canary from Mon Mar 20, both founders' approvals for Tue May 2, 2028"
spec: SPEC-647
acceptance_criteria: [AC-T7]  # rollback leaves clients polling; runs persist
risk_zone: red
status: in-progress
branch: s38-p10-t54
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T54
---

## Objective
The runbook is rehearsed on staging and the flip request carries the passing journeys, the shadow
evidence and both approvals.

## Plan (red)
- Runbook `docs/runbooks/runtime-v2-flip.md`: the three flags in order (`agent_runtime.v2`,
  `realtime.sse`, `engagement_run.enabled`), rollback in reverse (flags off; runs persist), the
  shadow and canary, the request, the flip, the rehearsal.
- `abacus_tools.runtime_v2_flip`: `render` writes the three one-flag requests; `check` holds the
  plan (order, one firm, the M17 slot, J11 and J23, both founders, the runbook's rollback, flag
  expiry after the slot, shadow floors 14 days / 50 runs / no invariant failure, canary since Mar
  20).
- `flip_request._FILE` accepts an optional `-<n>` so three requests share one date and firm.
- Rollback: revert; no data or flag changes.

## Built
- The runbook, the module, the filename rule, `tests/unit/tools/test_p10t54_runtime_flip.py` (20
  pass). DEC-4413.

## Partial (status in-progress)
- The staging rehearsal, the shadow run and the canary need staging (from Mon Mar 20, 2028); the
  real request needs the founders' approvals. The registry entries expire 2027-05-07, so `check`
  refuses the plan until P-10-T56's renewal (that is by design).

## Progress log
- 2026-11-12 (TASK-7429): `runtime_v2_flip shadow` builds shadow.json from the database; left:
  the staging rehearsal, the shadow window itself, the canary and both approvals.
- 2026-11-12: built; tests pass.
