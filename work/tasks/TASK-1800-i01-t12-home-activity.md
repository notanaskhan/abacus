---
id: TASK-1800
title: Home client activity projection (I-01-T12)
spec: docs/contracts/home-and-gates.md
acceptance_criteria: [AC4.3, AC4.4]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T12
branch: s13r-i01-t12
created: 2026-10-28
updated: 2026-10-28
---

## Objective
HOME-01's "Client activity": a rebuildable `home_activity_items` projection of allowlisted outbox events (client uploads, follow-ups sent, letters recorded, agent pre-screens), identifier and enum facts only, read through `visible()` so a walled client never shows, pruned after 90 days.

## Plan (amber)
- Migration `0320_home_activity_items` (`practice`): forced RLS, `source_event_id` unique per firm, CHECKs on `event_type` and `actor_kind`, size-capped jsonb refs and facts; app role inserts and deletes, never updates.
- `practice/activity.py`: allowlist `SOURCES`, projector `project` (insert on conflict do nothing, audited `home_activity.projected`), `rebuild_home_activity`, `prune_firm`/`prune_once` (audited `home_activity.pruned`), read `client_activity` under `visible(engagement.read_metadata)`.
- `practice/jobs.py`, `workflows.py`, `api.py`: SUBSCRIPTIONS, `HomeActivityPruneWorkflow` on `home_activity_prune:platform` (daily, background), history `home-activity-prune-v1-pruned.json`.
- Kernel: `relay.published_events` (one firm's published events through the relay role) for the rebuild; tool `python -m abacus_tools.reproject_home_activity <tenant>`.
- `GET /v1/home` fills `client_activity` (first 20, labels at read time). No contract shape change.
- Registries: worker module list, platform schedule lists, reviewed audit fallback list.
- Tests: `tests/integration/backfill/test_i01t12_home_activity.py`; replay in `tests/workflows/test_platform_jobs_replay.py`.
- Rollback: revert; 0320 downgrade drops the table (a projection: nothing lost).
- DEC-900.

## Progress log
- 2026-10-28: built; tests run in the end-of-batch pass (S13 leftovers).
