---
id: TASK-7315
title: "P-10-T46: Real eval runs of runtime.conformance on the direct and Bedrock routes in the evaluation account, HMAC-signed reports, evals/baselines.yaml cost rows"
spec: SPEC-647
acceptance_criteria: [AC-EV6]
risk_zone: red
status: in-progress
branch: s37-p10-t46
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T46
---

## Objective
Committed Bedrock and direct reports meet every section 6 threshold, and cost per case is recorded
as the baseline.

## Built
- `backend/src/abacus_tools/evals/runtime_conformance_real.py`: the real route's report shape,
  per-case cost and median, `clearance` (thresholds, DE cases, errors, cost within 10 % of the
  `runtime.conformance` baseline row, no row fails closed; only Bedrock clears for production),
  HMAC-SHA256 signing and verification (`ABACUS_EVAL_SIGNING_KEY`).
- `python -m abacus_tools.evals --agent runtime_conformance --route direct|bedrock` dispatches
  there and refuses without the evaluation account's stack.
- Test: `backend/tests/unit/tools/evals/test_p10t46_conformance_real.py`.

## Partial (status in-progress)
- The stack-bound loop (seed the synthetic firm's runs, call `run_conformance` per case on the
  route, rebuild each trajectory, grade, read the gateway's cost) and the two committed reports
  need the evaluation account's credentials and spend: an ops step. `evals/baselines.yaml`'s row is
  recorded by a person from the first signed Bedrock report (protected file).

## Progress log
- `2026-11-12` — Report, gate and signing built (S37); the real runs wait for the evaluation
  account.
