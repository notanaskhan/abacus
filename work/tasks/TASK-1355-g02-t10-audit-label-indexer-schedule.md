---
id: TASK-1355
title: The AuditLabelIndexer Schedule (G-02-T10 follow-up; DEC-436, DEC-453)
spec: SPEC-349
acceptance_criteria: [AC-6, AC-11]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T10
branch: s10c-red
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Wire the 60-second `AuditLabelIndexer` Temporal Schedule that TASK-1331 left out (DEC-436), so
the label index keeps up without a search; keep the on-search catch-up as the fallback.

## Plan
- `audit_trail/workflows.py`: `AuditLabelIndexerWorkflow` (type `AuditLabelIndexer`, v1), one
  activity `audit_trail.index_labels`, 5-minute timeout, three attempts; `LABELS_ID =
  "audit_labels:platform"`.
- `audit_trail/jobs.py`: `index_labels_activity` runs `labels.index_batch` for every firm, at most
  five batches of 2,000 per firm per run; a firm whose indexer lock is held (a search catching
  up) is skipped this run; a firm that fails is logged by id and the others still run.
  `WORKFLOWS` (background), `ACTIVITIES`, `SCHEDULES` (every 60 s; overlap SKIP and the one-hour
  catch-up window come from `PlatformSchedule`).
- `explorer.py` keeps `catch_up` before a search (the fallback); docstrings in `labels.py` and
  `api.py` say so.
- **Exact lists**: `test_platform_schedules.py` (`IDS`, `BACKGROUND`, the facts),
  `test_canary_checks.py` (declared Schedules), `test_platform_jobs_replay.py` (`AUDIT_JOBS`).
- **Replay** (ADR-090): `audit-labels-v1-indexed.json` recorded by
  `abacus_tools.workflows.record_platform_jobs` (stub activity); a later change goes behind
  `workflow.patched`.
- **Test**: `test_dec453_the_scheduled_run_indexes_every_firm_and_skips_a_busy_one`.
- **Runbook**: RB-34.
- No migration, flag or matrix row. Rollback: revert and delete the Schedule
  (`abacus_tools.schedules delete --id audit_labels:platform`, an ops task); searches keep
  catching up on their own.

## Progress log
- 2026-10-27: planned and built (S10 wave C); history recorded against throwaway containers.
- 2026-10-27: targeted pass green (labels, schedules, replay, canary list).
