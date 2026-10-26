---
id: TASK-1291
title: Audit-log contract stub (ADM-07 family) - classified models, 501 routes behind audit_log.explorer, fixtures, docs/contracts/audit-log.md v1
spec: SPEC-349
acceptance_criteria: [AC-1, AC-2, AC-5, AC-7, AC-8, AC-10, AC-12]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T04
branch: s9c-governance
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Contract first for ADM-07 (G-02-T04): the shapes, routes, flag gate and fixtures, so the AC suite
(T05) and the screen (T13) build against them before the read side (T08) exists.

## Plan
- `audit_trail/audit_log_contract.py`: `AuditEventRow`, `AuditEventDetail`, `ValueRow`,
  `AuditExport` and their parts, every field classified (request context and values
  `confidential`, the link `restricted`). Routes `GET /v1/audit-events`, `GET /{seq}`,
  `POST /exports` (202, `Idempotency-Key`), `GET /exports/{export_id}`, `POST
  /exports/{export_id}/link`, one matrix action each; `audit_log.explorer` off → 404, on → 501.
  Mounted in `audit_trail.api.ROUTERS`. No PUT, PATCH or DELETE.
- `docs/contracts/audit-log.md` v1 and its README row; `make generate`; the route-introspection
  suite regenerated.
- Provider stub tests `tests/contracts/audit_log/test_audit_log_contract.py`.
- Fixtures (fixture mode serves ADM-07 a to g): `apps/web/src/fixtures/seed/audit-log.ts` (the
  handoff's 14 rows, the Copperleaf drawer for Margaret and Felix, d's policy rows, the export),
  `handlers/audit-log.ts`, `scenarios/ADM-07.ts` and `contracts/audit-log.contract.test.ts`.
- No migration, no matrix row (T02 has them). DEC-417 records the shape choices.
- Rollback: revert; the flag stays off.

## Progress log
- 2026-10-26: built. 33 provider tests and 11 fixture tests green; api-client regenerated.
