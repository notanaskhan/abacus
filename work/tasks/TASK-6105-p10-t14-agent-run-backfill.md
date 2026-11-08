---
id: TASK-6105
title: "P-10-T14 legacy agent run backfill: AgentRunBackfill, migration 0711, the pipeline start tool"
spec: SPEC-000  # row (P-10-T14)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T14
branch: s30-p10-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
SPEC-647 §4.4: a throttled batch workflow giving every pre-v2 agent run its state (completed to succeeded, escalated to needs_input with reason escalated), a run number and a session link; started by the pipeline after 8 pm CT; resumable; replay histories.

## Plan
- Migration 0711 on 0710: `agent_runs_forward_only` lets through exactly a backfill write (state from NULL, nothing but state/state_reason/run_number/session_id changing); `agent_runs_state_sync` keeps status on such a write and accepts only the legacy mapping; a run number never changes; `GRANT UPDATE (run_number)`. Downgrade restores 0680's functions.
- `agents/run_backfill.py`: `backfill_batch(tenant, limit)` in one system unit of work (`FOR UPDATE SKIP LOCKED`, numbers from `tenant_counters.agent_run` seeded past any v2 number, session links through a workbench port, one `agent_runs.backfilled` audit event per batch); activity `agents.backfill_run_batch`.
- `agents/run_backfill_workflow.py`: `AgentRunBackfill` (background class), throttle sleep, continue-as-new every 200 batches.
- `workbench/run_links.py` + `register_session_links`: agents never reads `session_items`.
- `abacus_tools/agent_run_backfill.py`: per-firm start with id `agent_run_backfill:<tenant>`, refuses before 8 pm CT without `--now`.
- `abacus_tools/workflows/record_agent_run_backfill.py` and `tests/workflows/test_agent_run_backfill_replay.py`; `tests/integration/test_p10t14_agent_run_backfill.py` (2,400 runs, resume, audit, trigger refusals).

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2703
