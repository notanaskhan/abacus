---
id: TASK-6830
title: "A-07 remainders after S36: AUD-18 manifest live; what still waits on staging, the founders or other epics"
spec: SPEC-644
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
branch: s36f-a07-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-12
updated: 2026-11-12
plan_key: A-07-T50
---

## Built
- AUD-18's manifest entry is `live`; its screen contract was updated (DEC-3421).

## Not buildable here (recorded, not claimed)
- **A-07-T50:** the full-stack and staging walks of j03 9b–19, j04 12 and j18 5–6 wait for the
  deploy with the three A-07 flags on for PF-X1 (`test.fixme` names it). Fixture mode passes
  (40 journeys, TASK-6827).
- **A-07-T51:** the rehearsal, shadow, restore drill and both founders' approvals need staging
  (DEC-3415, `last_rehearsed: never`).
- **A-07-T52:** docs are done. The flag retirement rides the Apr 25, 2028 train (DEC-3416); the
  capacity actuals are in S36's status file.
- **P-10-T41's real routes:** these are P-10-T46 (S37, red): real-model runs in the evaluation
  account, which cost money and need the Bedrock route. Not run.

## Progress log
- `2026-11-12` — Manifest flip; routes vitest 63 passed.
