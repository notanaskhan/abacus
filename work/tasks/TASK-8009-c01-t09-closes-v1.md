---
id: TASK-8009
title: "C-01-T09: migration closes_v1 — record, plans, versions, rows, templates, procedures"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: c01-t09-closes-v1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T09
---

## Objective
migration closes_v1 — record, plans, versions, rows, templates, procedures.

## Plan
1. [x] Migration 0881 on 0880, expand-only: columns on `closes`; tables close_plans, close_plan_versions, close_plan_rows, close_request_templates, close_templates, close_procedures via `tenant_table()`; checks, partial unique draft index, freeze and forward-only triggers (epic §4.2 T09).
2. [x] `closes/registry.py` columns; retention record type `cas_workpaper` (7 years, GOVERNANCE).
3. [x] Downgrade drops only what it added.
Rollback: downgrade; no data before T14.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: migration **0881** (on 0880). `closes` lifecycle columns with the pin, on-hold and locked checks and the `closes_plan_pinned` trigger (QC-2); `close_plans`, `close_plan_versions` (one-draft partial index, human-only publish CHECK, `close_plan_version_frozen` trigger raising `plan_version_frozen` / `unadopted_rows`), `close_plan_rows` and `close_request_templates` (frozen with their version), `close_templates` (insert-only), `close_procedures` (forward-only trigger; one row per step attempt). Grants follow `closes/registry.py`; `tests/security/test_tenant_isolation.py` lists the six tables. Not run (end pass: up/down/up, schema_check, single head).
- **Partial.** The retention record type `cas_workpaper` is a published floor-set row (Q-02-T23 staff floor routes): content, not schema, so it is loaded through those routes, not this migration (DEC-5004).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5004 | `cas_workpaper` retention is floor-set content, not migration | no |
