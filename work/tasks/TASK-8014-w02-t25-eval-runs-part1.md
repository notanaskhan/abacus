---
id: TASK-8014
title: "W-02-T25 part 1: workbench.assistant eval runs on the fake model, real-route runner, cost baseline"
spec: SPEC-653
acceptance_criteria: []
risk_zone: red
status: in-review
branch: w02-t25-eval-runs-part1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: W-02-T25
---

## Objective
Eval runs for `workbench.assistant`: fast subset on PRs, nightly full suite on FakeModel, full
real runs on the direct route and Bedrock with HMAC-signed reports, and the cost row.

## Plan (red: written before the build)
1. [x] `make evals-workbench-fast` in CI's agents step; `make evals-workbench-full` in the nightly evals workflow.
2. [x] `abacus_tools/evals/workbench_assistant_real.py`: cost median, fail-closed clearance against `evals/baselines.yaml`, HMAC signing; `--route direct|bedrock` wired in `__main__`.
3. [x] `evals/baselines.yaml` row `workbench.assistant: {medium: "0.60"}` (protected).
4. [ ] The real runs themselves: the evaluation account's stack and credentials (like P-10-T46 and I-02-T20).
5. [ ] Session-plan cases (W-02-T19, S43 #1953) join the suite when T19 merges.

## Progress log
- `2026-11-14` — Part 1 built; `backend/tests/unit/evals/test_w02t25_workbench_real.py` (not run). AC "committed Bedrock and direct reports meet every threshold" waits on the evaluation account (DEC-5005).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5005 | Fake-model runs wired now; real runs refuse until the evaluation account runs them | no |
