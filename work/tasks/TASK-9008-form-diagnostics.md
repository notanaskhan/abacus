---
id: TASK-9008
title: "T-06-T50: Diagnostics service"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t06-t50-diagnostics
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: T-06-T50
---

## Objective
Diagnostics on Ridgeline create no new issue when a matching TXP-10 issue exists, and the download writes one form_preview.downloaded event.

## Done
- tax/form_diagnostics_run.py: code rules (the checklist's pure checks and the Item L identity) plus the engine's newest diagnostics, upserted per approved checkpoint; a failing rule links the open issue under its reference before raising one
- GET diagnostics refreshes first
- tests: 3 (TXP-10 issue linked not duplicated on Postgres; engine rule naming; empty return fails only the representative)
- DEC-6014

## Progress log
- `2026-11-26` — Built. Trace and the audited download (one form_preview.downloaded event) are S53's routes.
