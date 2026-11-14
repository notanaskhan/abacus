---
id: TASK-8003
title: "C-01-T03: close status registry rows and copy registries (DF-23)"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: todo
branch: c01-t03-status-rows
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T03
---

## Objective
close status registry rows and copy registries (DF-23).

## Plan
1. [ ] `docs/product/status-vocabulary.yaml` / status registry: `close` six states (not_started, in_progress, in_review, approved, delivered, locked) plus the on-hold side flag; `close_plan_version` draft · published · discarded; `close_procedure` queued · running · needs_attention · done · failed; `reconciliation` tally pending · tie · off; `analytic_line` statuses; `transaction_question` open · answered · withdrawn.
2. [ ] Regenerate StrEnums, OpenAPI enums and `status.ts`.
3. [ ] Copy registries for the close screens (UI strings verbatim from the handoff).
Rollback: revert; no consumer reads the rows before T14.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
