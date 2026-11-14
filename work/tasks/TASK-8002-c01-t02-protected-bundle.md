---
id: TASK-8002
title: "C-01-T02: S44 protected bundle — closes matrix, four flags, entitlement, registries, glossary"
spec: SPEC-655
acceptance_criteria: []
risk_zone: red
status: in-review
branch: c01-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T02
---

## Objective
S44 protected bundle — closes matrix, four flags, entitlement, registries, glossary.

## Plan
1. [x] `docs/architecture/permission-matrix/closes.yaml`: close.*, close_run.*, close_plan.*, close_template.import, arrangement.edit, reconciliation.resolve_item, flux.*; `requests.yaml` transaction_question.send/.answer/.read_own; `connections.yaml` ledger.sync_now. Agent `task_scope` only for suggestion.create, issue.create, decision_card.raise (existing rows); portal deny on every firm route.
2. [x] `docs/architecture/feature-flags/closes.yaml` (closes.engine, closes.portal_requests, closes.agent) and `connections.yaml` (connections.ledger_sync): default off, expiry 2028-08-29.
3. [x] `closes` module entitlement row (`platform/entitlements.py` + data migration if the catalogue needs one).
4. [x] TABLE_OWNERS, IMMUTABLE_TABLES (insert-only tables of T09/T10), MODULE_DEPENDENCIES edges for closes; worker MODULES already lists closes.
5. [x] Glossary rows (epic §4.8).
6. [x] Regenerate `_matrix.py`, `_flags.py`, `actions.gen.ts` and the generated matrix tests.
Rollback: revert the PR; every flag is default off and no route mounts yet.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built. Matrix: `closes.yaml` (19 actions), `requests.yaml` (transaction_question.send, .read_own, .answer), `connections.yaml` (ledger.read, ledger.sync_now). Flags `closes.engine`, `closes.portal_requests`, `closes.agent` (closes.yaml) and `connections.ledger_sync` (connections.yaml), created 2026-11-14, expiring 2027-05-13 under DEC-137 (the plan's Jun 29 – Aug 29, 2028 dates mapped onto the solo calendar). Entitlement `closes` in `platform.entitlements` with migration **0880** (on 0871) widening `tenant_entitlements_module_check`. Module edges closes → practice, connections. Glossary section "close engine". Regenerated `_matrix.py`, `_flags.py`, `actions.gen.ts`, the generated matrix tests. Test `tests/unit/closes/test_c01t02_protected_bundle.py` (not run; end pass).
- **Partials.** QC-3 (staff start runs and incorporate only with `close_preparer`): `function_in` binds every allowed role in a rule, so staff is denied until the compiler has a per-role condition (proposed for review; fail closed). TABLE_OWNERS and IMMUTABLE_TABLES come from `closes/registry.py` and land with each table's migration (T09, T10), since `schema_check` fails a listed table that does not exist. Migration 0880 sits on 0871; S43's 0872 (#1953) also does, so whichever lands second re-chains at the batch merge.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5002 | QC-3 fails closed: staff denied until a per-role function condition exists | no |
