---
id: TASK-2339
title: P-04 review.approve_agent_output flag gating SHL-10 decisions (P-04-T46 follow-up)
spec: SPEC-360
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T46
branch: s18-p04-flag
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
P-04 §2 names `review.approve_agent_output` as the per-firm rollout flag for SHL-10's live approval
(flip Tue Jul 13, 2027); it was never created (DEC-1384). Create it and gate SHL-10's decisions on it,
so the Jul 13 runbook can run.

## Plan
Red (the decision path). `docs/architecture/feature-flags/review.yaml` + regenerated
`kernel/_flags.py`; `agents/contract.py`: `_deciding` (C3 flag then the approval flag; 404) on
approve, reject, route and follow-up; `_shown` drops decision actions from the view while off; reads
and Undo unchanged. Turned on wherever the C3 flag is turned on for decision work: the Dev seed, the
Brightwater Hale loader, `review_support.py`, `p04t28_support.py`, the P-04-T25 adapters suite.
`tests/unit/agents/test_p04t46_approval_flag.py`; runbook §0/§3/§5 updated; DEC-1385. Rollback:
revert (the flag then disappears and decisions answer behind the C3 flag alone).

## Progress log
- `2026-10-31` — built; unit 4/4; review integration suites run in the end review. `[skip ci]` until
  the merge, which runs CI.

## Handoff
- **Current state:** PR open.
- **Exact next step:** end review, merge with CI.
