---
id: TASK-2338
title: P-04-T46 flip plan for SHL-10 live approval (Tue Jul 13, 2027)
spec: SPEC-360
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T46
branch: s18-p04-t46
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Flip plan for review.approve_agent_output on Tue Jul 13, 2027: docs/runbooks/review-approvals-flip.md
(rollback is flag off; decisions persist), staging journey and shadow-comparison evidence, both
founders' approvals." Acceptance: "The runbook is rehearsed on staging and the flip request carries
the passing journey, the shadow evidence and both approvals."

## Plan
`docs/runbooks/review-approvals-flip.md` (preconditions, evidence pack, flip, verify, rollback);
DEC-1384. Docs only. Found: the flag `review.approve_agent_output` was never created; SHL-10 sits
behind `review.grammar_api`, so the runbook names the gap as its §0 blocker.

## Progress log
- `2026-10-31` — written. Open (human): the flag itself (a red code change to the approve path),
  the staging rehearsal, both approvals. `[skip ci]`.

## Handoff
- **Current state:** PR open, held for the batch.
- **Exact next step:** end review.
