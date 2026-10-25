---
id: TASK-1233
title: Temporal Schedules for platform jobs; spend-anomaly and notification-purge loops moved off the interactive worker (Q-01-T26)
spec: SPEC-050
acceptance_criteria: [AC-21]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T26
branch: s8b-platform-ops
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Two interactive workers run with no duplicate side jobs, and replay tests pass for both moved jobs" (Q-01-T26). Q-01 §4.5: `SpendAnomalyWorkflow` (`spend_anomaly:platform`, hourly, background) and `NotificationPurgeWorkflow` (`notification_purge:platform`, daily, background) replace the worker's side loops; Schedules use overlap `SKIP` and a 1 h catch-up window; `kernel.dispatch` owns `schedule`, `pause`, `unpause` and `delete` (DISPATCH-001). Platform jobs only (Q-01 §11 R9: P-50 governs firm-facing agent schedules later on the same primitive).

## Plan (red zone)
- **Kernel:** `kernel/dispatch.py` gains `PlatformSchedule` (id, workflow, every) and `schedule()` (create, or update the action, spec and policy of an existing one while keeping its paused state), `pause()`, `unpause()`, `delete()`, `describe_schedule()`. Overlap `SKIP`, catch-up window 1 h, the workflow on its class's queue. No other file names `create_schedule` or `ScheduleActionStartWorkflow` (DISPATCH-001 already bans both outside `kernel/dispatch.py`).
- **Workflows:** `platform/jobs.py` `SpendAnomalyWorkflow` (activity `platform.flag_spend_anomalies` over `ai_gateway.budgets.flag_anomalies`, one pass); `notifications/purge.py` `NotificationPurgeWorkflow` (activity `notifications.purge_expired`, one pass of the existing purge with its audit event). Both `background`, both declared in their module's `api.py` (`WORKFLOWS`, `ACTIVITIES`, new `SCHEDULES`). Versioning: v1 histories (ADR-090).
- **Worker:** `run()` no longer starts the anomaly or purge loops; only the relay stays beside the interactive pool. `run_anomaly_job` is removed; `run_purge_job` stays as a loop over `purge_once()` for the SPEC-013 back-fill test.
- **Who creates the Schedules:** `python -m abacus_tools.schedules ensure` (idempotent; run by the deploy after migrate, Q-01-T18) and `show | pause | unpause | delete --id --operator --reason` for operators. Locally `make schedules`.
- **Legacy queue:** `serve_legacy_queue` stays a setting (default true locally); staging and production render `ABACUS_SERVE_LEGACY_QUEUE=false` in their task definitions once the drain query is empty (RB-01 step; no Terraform service exists yet, so it is a human to-do).
- **Tests:** `tests/unit/kernel/test_dispatch_schedules.py` (fake client: create, update keeps state, pause/unpause/delete, SKIP and 1 h, queue by class); `tests/unit/worker/test_worker_main.py` (the worker starts no anomaly or purge loop); `tests/integration/test_platform_schedules.py` (real Temporal dev server: ensure twice gives one Schedule, a trigger runs the job once on the background queue, paused stays paused across ensure); `tests/workflows/test_platform_jobs_replay.py` with histories recorded by `abacus_tools.workflows.record_platform_jobs`; the platform workflow inventory in `tests/integration/test_tenant_provisioning.py` extended.
- **Rollback:** revert the commit; the worker's loops come back. Schedules already created are deleted with `abacus_tools.schedules delete`.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built. `kernel.dispatch` gains `PlatformSchedule`, `schedule` (create or converge, keeping the paused state), `pause`, `unpause`, `delete`, `describe_schedule`; `SpendAnomalyWorkflow` (platform/jobs.py) and `NotificationPurgeWorkflow` (notifications/purge.py), both background, with `SCHEDULES` in their `api.py`; the worker runs only the relay beside the interactive pool; `run_anomaly_job` removed; `abacus_tools.schedules ensure|show|pause|unpause|delete` and `make schedules`. Histories `spend-anomaly-v1-flagged.json` and `notification-purge-v1-purged.json` recorded by `abacus_tools.workflows.record_platform_jobs`. Tests: `tests/unit/kernel/test_dispatch_schedules.py` (7), `tests/unit/worker/test_worker_main.py` (+1: two interactive workers run no side job), `tests/integration/test_platform_schedules.py` (4, real dev server: ensure twice, pause survives, a trigger with two pools runs each job once, delete and re-ensure), `tests/workflows/test_platform_jobs_replay.py` (3); platform inventory in `test_tenant_provisioning.py` extended. The Schedules are not created on staging until the deploy runs `abacus_tools.schedules ensure` (Q-01-T18). Human to-do: render `ABACUS_SERVE_LEGACY_QUEUE=false` in the staging worker task definition once `temporal workflow list --query "TaskQueue='abacus' AND ExecutionStatus='Running'"` is empty (no ECS service is in Terraform yet).
- 2026-10-25: follow-up: Q-01-T46's `DrainSesEventsWorkflow` had no starter; it is now the Schedule `ses_events:platform` (every minute, time_sensitive) declared in `communications/api.py`, with `ses-drain-v1-drained.json` recorded by the same recorder (which now records only missing histories). DEC-359.
