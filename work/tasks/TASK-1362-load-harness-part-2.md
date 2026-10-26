---
id: TASK-1362
title: Load harness part 2, the chapter 10 scenarios and the x1 smoke trend (Q-03-T043)
spec: docs/plan/10-quality-strategy.md section 10.11.3 and 10.11.5
acceptance_criteria: ["The x1 smoke runs after two consecutive staging batch deploys and posts its trend to the quality report."]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T043
branch: s10c-ops
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The chapter 10 section 10.11.3 scenarios as harness profiles, a dry-run mode, and the x1 smoke's
p95 trend that opens a ticket past +20% over its 4-week median and feeds the quality report.
Added to the S10 wave C list by the main session on 2026-10-27.

## Plan
- **Profiles** (`loadtest/scenarios/`): `monday_9am` (ramped sign-in wave, Home, lists with
  counts, record reads), `deadline_surge` (portal sign-in burst, client and request reads),
  `pbc_import_fairness` (Brightwater Hale's 300-item import beside load firm 1, targets on the
  other firm), `sse_soak` (2 h on the polling fallback: no stream route until P-15),
  `backfill_business_hours` (Monday mix plus Temporal visibility; the backfill is the operator's),
  `failure_under_load` (Monday mix through a task kill and a failover, by hand), `x1_smoke`
  (5 min, read-only). Targets from 10.11.1 only (300 ms record read, 500 ms list with counts),
  error ceiling 0.1%.
- **Harness (additive):** `Scenario.ramp_seconds` (users start evenly over it) and `--dry-run`
  (`run.dry_run`: the plan with ids filled; no client, no connection; `make loadtest DRY_RUN=1`).
  The loopback and local-environment refusal (DEC-397) is unchanged.
- **Trend:** `loadtest/trend.py` (newest x1 smoke against the median of the runs in the 4 weeks
  before it, at least two; +20% writes a results-only ticket body and exits 1) and
  `quality.report.load_rows` (`loadtest-trend.json` among the inputs; Ops row).
- `journey_vars` gains `fleet_engagement_id` (load firm 1's first audit).
- **Tests:** `tests/unit/tools/test_q03t043_scenarios_and_trend.py`.
- **Runbook:** `docs/ops/loadtests/README.md` section 4 (each scenario, the human's part, the
  post-deploy x1 smoke and trend), and the skill.
- **Rollback:** revert; nothing runs by itself.

## Not done (human or later tasks)
- Running any scenario at scale: the perf stack and its runner (Q-03-T036). The post-deploy job
  that runs `x1_smoke` and the trend after each staging batch deploy is a deploy-workflow step for
  the builder; the acceptance (two consecutive deploys) is the runbook's.
- Uploads at the peak rate, 8879 sends and K-1 releases in `deadline_surge`; SSE streams in
  `sse_soak` (P-15). Each profile's header says so.
- No local smoke against the compose stack was run in this session (no `make dev` running); the
  dry run was run for every profile.

## Progress log
- 2026-10-27: built (DEC-455 covers the harness additions).
