---
id: TASK-8009
title: "C-01-T09: migration closes_v1 — record, plans, versions, rows, templates, procedures"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: todo
branch: c01-t09-closes-v1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T09
---

## Objective
migration closes_v1 — record, plans, versions, rows, templates, procedures.

## Plan
1. [ ] Migration 0881 on 0880, expand-only: columns on `closes`; tables close_plans, close_plan_versions, close_plan_rows, close_request_templates, close_templates, close_procedures via `tenant_table()`; checks, partial unique draft index, freeze and forward-only triggers (epic §4.2 T09).
2. [ ] `closes/registry.py` columns; retention record type `cas_workpaper` (7 years, GOVERNANCE).
3. [ ] Downgrade drops only what it added.
Rollback: downgrade; no data before T14.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
