---
id: TASK-1043
title: C5 section portal-pbc consumer contract tests on behalf of R-01, T-02, C-01 and A-09 (R-01-T02)
spec: SPEC-323
acceptance_criteria: [AC-4]
risk_zone: amber
status: done
epic: R-01
plan_key: R-01-T02
branch: s7-r01-portal-requests
created: 2026-10-24
updated: 2026-10-24
---

Plan of record: R-01 (docs/plan/epics/R-01.md §8.2); docs/contracts/portal-pbc.md.

## Objective
"The suite runs in N's CI against the stub and fails if any portal field carries a firm status
code, an amount or an agent reference." Consumer tests for the portal-pbc section, written from
the screen contracts (POR-03, POR-04, POR-14) on behalf of R-01, T-02 (POR-05's upload fallback),
C-01 (POR-11 rows and the question slot) and A-09 (POR-23's room).

## Plan (amber: tests only)
- `backend/tests/contracts/c5_portal_pbc/test_c5_portal_pbc_consumers.py`: every portal answer is
  the contract model; no schema reachable from a portal answer has a field that names a firm
  status, an amount, a balance, materiality, a currency, a confidence, a score, a screening
  verdict or an agent, nor reaches a status-registry enum (the firm's codes); a planted model
  proves the check fails; `client_status` is exactly the registry's client labels; one receipt
  kind and one `allowed_actions` vocabulary, each named in the contract; the room's shape is its
  delegated items only (no binder, category, other party or client-wide count); the suggest sees
  file names only; drop outcomes and refusals; the read grants no firm role; the contract names
  every human-only action, audit event, consumer and error code.
- `apps/web/src/fixtures/contracts/portal-pbc.contract.test.ts`: Brightwater Hale fixtures typed
  with the generated client (a type-level `Clean<T>` over every portal answer and exact-union
  checks of the three vocabularies) and validated against the OpenAPI document; run-time refusals
  of a firm status word, an amount, a confidence, an agent field, an unknown action and anything
  outside the room's delegated shape.
- Rollback: delete the two files.

## Progress log
- 2026-10-24: both halves written and green against the stub (pytest 33, vitest 14); tsc,
  eslint, ruff, pyright clean.
