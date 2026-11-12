---
id: TASK-7415
title: "T-04-T43: Real eval runs of the tax suites on the direct and Bedrock routes in the evaluation account: HMAC-signed reports, baselines cost rows, route parity under 90 days, clearance recorded per capability"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: red
status: in-progress
branch: s38-t04-t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T43
---

## Objective
The Bedrock reports meet every frozen threshold or the capability stays synthetic-only with the
failing grader named, and cost per case sits within ADR-070's +10% gate.

## Built
- `backend/src/abacus_tools/evals/tax_return_real.py`: per-capability `capability_clearance`
  (`client_data: cleared` only with every frozen threshold, no zero-tolerance failure, no error,
  median cost within 10 % of the baselines row, Bedrock, parity under 90 days; every reason named
  otherwise), `below_thresholds` (an unmeasured grader is below), `parity_fresh`, the signed
  `report` (the conformance signer), `real_main` refusing without the evaluation account's stack.
- `python -m abacus_tools.evals --agent tax_return --route direct|bedrock` dispatches there.
- Tests `backend/tests/unit/tools/evals/test_t04t43_tax_real.py` (14 pass).

## Partial (status in-progress)
- The runs themselves (seed the synthetic households, run each case's capability on the route,
  rebuild the trajectory, grade, read the gateway's cost) need the evaluation account's credentials
  and spend: an ops step, as P-10-T46's. The baseline rows are recorded by a person from the first
  signed Bedrock report (protected file). Real TRI still needs G-5 to G-7 per firm and taxpayer.

## Progress log
- `2026-11-12` — Report, clearance and signing built (S38); real runs wait for the evaluation account.
