---
id: TASK-2206
title: P-11-T04 C11 consumer contract tests
spec: SPEC-520
acceptance_criteria: [AC-32, AC-28]
risk_zone: amber
status: todo
epic: P-11
plan_key: P-11-T04
branch: s17-p11-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
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

## Progress log
- `2026-10-29` — Planned in P-11-T01.
