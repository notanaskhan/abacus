---
id: TASK-8002
title: "C-01-T02: S44 protected bundle — closes matrix, four flags, entitlement, registries, glossary"
spec: SPEC-655
acceptance_criteria: []
risk_zone: red
status: todo
branch: c01-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T02
---

## Objective
S44 protected bundle — closes matrix, four flags, entitlement, registries, glossary.

## Plan
1. [ ] `docs/architecture/permission-matrix/closes.yaml`: close.*, close_run.*, close_plan.*, close_template.import, arrangement.edit, reconciliation.resolve_item, flux.*; `requests.yaml` transaction_question.send/.answer/.read_own; `connections.yaml` ledger.sync_now. Agent `task_scope` only for suggestion.create, issue.create, decision_card.raise (existing rows); portal deny on every firm route.
2. [ ] `docs/architecture/feature-flags/closes.yaml` (closes.engine, closes.portal_requests, closes.agent) and `connections.yaml` (connections.ledger_sync): default off, expiry 2028-08-29.
3. [ ] `closes` module entitlement row (`platform/entitlements.py` + data migration if the catalogue needs one).
4. [ ] TABLE_OWNERS, IMMUTABLE_TABLES (insert-only tables of T09/T10), MODULE_DEPENDENCIES edges for closes; worker MODULES already lists closes.
5. [ ] Glossary rows (epic §4.8).
6. [ ] Regenerate `_matrix.py`, `_flags.py`, `actions.gen.ts` and the generated matrix tests.
Rollback: revert the PR; every flag is default off and no route mounts yet.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
