---
id: TASK-7422
title: "P-10-T51: runtime and SSE load test on staging (1,500 streams, 50 parallel engagement runs, commit to SSE p95 <= 2 s, RDS connections < 70%); SSE delivery SLO alarm; RB-28"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-T5]
risk_zone: red
status: in-progress
branch: s38-p10-t51
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T51
---

## Objective
The load report meets the targets or files dated fixes, and RB-28 is rehearsed with clients
falling back to polling.

## Plan (red)
- Measure delivery on the database clock (no writer/reader skew): the stream's read selects
  `abacus_now() - at` per row; the API logs `realtime.delivered` (counts and ms only) on tail
  reads, never on the replay after `Last-Event-ID`.
- Staging: a log metric filter (`Abacus/Realtime SseDeliveryLagMs`) and two alarms
  (`realtime_slo.tf`): SLO-06 p95 > 5 s for 15 min, and `DatabaseConnections` above 70% of
  `db_max_connections`. Plan only; applied with the S38 close's staging deploy.
- Load: `scenarios/runtime_v2.yaml` (1,500 streams over 250 synthetic subjects at the API's
  6-per-person cap, 50 users starting engagement runs once a minute, run reads); `Stream.subject_prefix`
  and the runner's `stream_tokens`; budgets `sse_commit_to_event` 2,000 ms and the 70% ceiling
  (`p10_budgets.runtime_report`).
- RB-28 runbook (triage, fallback by `realtime.sse`, the rehearsal steps).
- Rollback: revert the commit; the alarms are Terraform only; the log line is additive.

## Built
- `backend/src/abacus/modules/notifications/realtime.py`: `lag_ms` in the read; `realtime.delivered`.
- `backend/src/abacus_tools/loadtest/{scenario.py,run.py,p10_budgets.py,scenarios/runtime_v2.yaml}`.
- `infra/envs/staging/realtime_slo.tf`, three variables in `variables.tf`.
- `docs/runbooks/RB-28-realtime-delivery-degraded.md`; the runbook index row.
- Tests: `tests/unit/tools/test_p10t51_runtime_load.py`, `infra/tests/test_realtime_slo.py`,
  `tests/integration/test_p10t51_delivery_lag.py` (end pass).
- DEC-4412.

## Partial (status in-progress)
- The staging run, the load report and the RB-28 rehearsal need staging (the runner refuses a
  hosted target from a laptop; the pipeline's load job runs it) and 250 provisioned
  `loadtest-stream-*` staff on PF-X1. Staging's `db.t4g.micro` (about 87 connections) is below what
  1,500 streams need at 1 s reads; the load report will say whether the class must change.
- The outbox relay leg (event committed to `realtime_events` row) is the relay's own lag (RB-06),
  not in `lag_ms`.

## Progress log
- 2026-11-12: built; unit and infra tests pass (16 + 4); integration test left for the end pass.
