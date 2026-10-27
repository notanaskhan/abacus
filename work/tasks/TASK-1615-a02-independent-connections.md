---
id: TASK-1615
title: Independent AC tests for entity-scoped connections, reconnect requests and health (A-02-T29)
spec: SPEC-333
acceptance_criteria: [AC-35, AC-36, AC-39, AC-41, AC-44]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T29
branch: s13-a02-t29
created: 2026-10-27
updated: 2026-10-27
---

## Objective
An ADR-078 suite, written from the spec and contract, that fails on each seeded violation.

## Plan
- `backend/tests/integration/backfill/test_a02t29_independent_connections.py` on A-02-T16's world: authorization and fresh MFA, single-use and person-bound state, one live ledger (API and database), many feeds, disconnect keeps data, needs_reauth split, INV-4 (Tess Moreno and another client), agent and system refusal, portal person cannot ask the reconnect question. Health is A-02-T25's own suite.
- A-02-T16's `connected()` helper reads the additive `CompleteOut` (A-02-T28) by key; `c20-integrations.md` notes the additive fields.
- Rollback: revert.

## Progress log
- 2026-10-27: written; run in the batch pass. Not run against a planted mutation here (that is the batch pass's mutation check).
