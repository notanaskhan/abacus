---
id: TASK-7940
title: "I-02-T20: eval runs for briefing.today (fast on PRs, nightly full, signed direct and Bedrock reports)"
plan_key: I-02-T20
spec: SPEC-654  # I-02 §6.3
acceptance_criteria: [AC-3]  # committed Bedrock and direct reports meet every frozen threshold at ≤ $0.10 a briefing
risk_zone: red
status: in-review
branch: i02-t20-briefing-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
The cadence and the real-run report for `briefing.today`: fast subset on PRs, nightly full on
FakeModel, direct and Bedrock runs in the evaluation account with HMAC-signed reports, a cost
baseline row and recorded p95 latency.

## Plan (red)
- `abacus_tools/evals/briefing_today_real.py` (new): clearance, p95, judge mean, signed report,
  `real_main` refusing without the account's stack; `__main__` routes real runs to it.
- `Makefile` `evals-briefing-fast`/`-full`; `ci.yml` stage 3 step; `evals.yml` nightly step;
  `evals/baselines.yaml` `briefing.today: medium: "0.10"` (protected; the spec's budget).
- Tests: `backend/tests/unit/evals/test_i02t20_briefing_real.py`.
- Rollback: revert (the baseline row and the two steps go with it).

## Partial
- No committed Bedrock or direct report: the evaluation account's stack-bound loop is not wired
  (as T-04-T43 and P-10-T46), and DEC-1391 leaves real runs to that account. The run refuses
  rather than reporting what it did not measure.
- The ten Today ask cases for `evals/workbench_assistant` (I-02 §6.3) are not added: that suite's
  case format and frozen graders belong to W-02's suite owner row.

## Progress log
- 2026-11-14: built; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4935 | cadence, signed report, cap and baseline, judge floor, p95 recorded | no |
