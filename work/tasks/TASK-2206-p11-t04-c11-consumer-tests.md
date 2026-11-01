---
id: TASK-2206
title: P-11-T04 C11 consumer contract tests
spec: SPEC-520
acceptance_criteria: [AC-32, AC-28]
risk_zone: amber
status: done
epic: P-11
plan_key: P-11-T04
branch: s17-p11-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-11-01
---

## Objective
pytest against the C11 stub in `backend/tests/contracts/c11_renderer/` and TypeScript fixture
assertions that the T10 `DocumentVM` and the F-07 field manifest are satisfiable from C11.

Acceptance: "The suite asserts shapes, refusal codes (missing_variable, final_requires_approval,
document_locked), human-only actions and audit event names, and runs green in the provider's CI."

## Plan (amber)
Written from SPEC-520 and the contract, not the implementation: `test_shapes.py` (every route's
schema in the OpenAPI snapshot), `test_refusals.py` (the error codes in the contract's enum),
`test_human_only.py` (matrix: agent and client roles denied the human-only actions),
`test_audit_names.py` (the contract's event names registered); `apps/web/src/domain/documents/c11-to-vm.test.ts`
(a C11 GeneratedDocumentOut + fields map onto `DocumentVM` and a field manifest). Added to the
contracts CI shard. Rollback: revert.

As built: `backend/tests/contracts/c11_renderer/test_c11_consumer.py` (shapes, DF-31 words, field
manifest, the closed DocBlock vocabulary against the contract's §6, decimal-string table cells,
images by asset id, the three refusal codes and every §7 code, 409 on regenerate and publish,
human-only actions against §4 and the matrix, audit names equal to §5), with `AUDIT_EVENTS` and
`HUMAN_ONLY_ACTIONS` on the contract module; `apps/web/src/domain/documents/c11.ts` (C11 → the T10
header and the F-07 field placements) and `apps/web/src/fixtures/contracts/c11-renderer.contract.test.ts`
(the mapping on the seed fixture, and every fixture response validated against the OpenAPI shape).
`tests/contracts` already runs in `make ci-contracts` (the provider's CI).

## Progress log
- `2026-10-29` — Planned in P-11-T01.
- `2026-10-29` — Built on `s17-p11-t04` (stacked on T03); run at the S17 end review.
- 2026-11-01: merged to main in #746 (a2f684bb4).
