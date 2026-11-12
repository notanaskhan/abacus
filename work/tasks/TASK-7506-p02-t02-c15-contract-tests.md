---
id: TASK-7506
title: P-02-T02 C15 consumer contract tests
plan_key: P-02-T02
spec: SPEC-000  # contract C15 v1, docs/contracts/c15-search.md
acceptance_criteria: [AC-1]  # shapes, client and agent refusals, classification tags, POST-only search text, no wall count
risk_zone: amber
status: in-review
branch: p02-t02-c15-contract-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The C15 consumer suite, written from the contract: pytest in `backend/tests/contracts/c15_search/`
and the TS fixture assertions in `apps/web/src/fixtures/contracts/search.contract.test.ts`.

## Plan
- `backend/tests/contracts/c15_search/test_c15_consumer.py`: routes and actions on the OpenAPI
  document, 501 until P-02-T08 (`UNBUILT` shrinks with it), no other `/v1/search` path, no `q` in a
  URL, no `hidden`/`wall` property and no `hidden_by_wall` anywhere, `total_visible` ≤ 99, every
  field classified (titles and the query `confidential`, ids and counts `internal`), firm roles
  allowed and client roles, agent, system, QI and support refused, matrix before flag, flag off 404,
  the registration API on `platform.api`.
- `apps/web/src/fixtures/contracts/search.contract.test.ts`: SHL-02a's Returns row typed with the
  generated client and validated against the OpenAPI document; a wall count is refused; the cap;
  POST-only text.

## Partial
- The TS half reads the regenerated client (`make generate` at the S39 end pass).

## Progress log
- `2026-11-12` — Suites written (DEC-4506). They run at the S39 end pass.
