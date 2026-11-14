---
id: TASK-8021
title: "T-07-T07: migration fiduciary_core (expand-only)"
spec: SPEC-656
acceptance_criteria: []
risk_zone: amber
status: in-progress
branch: t07-t07-fiduciary-core
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-07-T07
---

## Objective
migration fiduciary_core (expand-only).

## Plan
Files: `backend/migrations/versions/0883_fiduciary_core.py` (on 0882): epic §4.2 M1 tables with `tenant_table()`, forced RLS, insert-only versions, the human-only CHECK on `sixty_five_day_elections`, citation CHECKs on determination versions, forward-only interpretation status trigger; `tax/fiduciary_models.py`, `tax/fiduciary_repository.py`; `tax/registry.py` TABLES / INSERT_ONLY / INSERT_COLUMNS; tenant-isolation list. Tests: `tests/unit/tax/test_t07t07_fiduciary_core.py` (registry and CHECK text); DB checks run at the end pass. Rollback: downgrade drops the new tables (expand-only, no data).

## Progress log

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
