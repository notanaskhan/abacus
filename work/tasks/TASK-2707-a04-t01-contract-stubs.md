---
id: TASK-2707
title: A-04-T01 workpaper core and audit planning contract stubs
spec: SPEC-000  # A-04-T01 row, A-04 §3, §4.3, §4.6 (the SPEC lands with A-04-T02)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T01
branch: s22-a04-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "The generated client exposes every A-04 operation behind its flag with examples
  footing 252,200 / 189,150 / 12,610, and the protected matrix, flag and status edits land."

## Scope
**In**: `docs/contracts/workpapers-core.md` and `audit-planning.md` (+ register rows); Pydantic
models with classification tags and 501 stubs for workpapers (states, record, versions, cells,
drafts, export, attention flags), procedures and program tailoring, materiality (current,
preview, proposals, reassessments), risks (register, linkage, drawer, edit, responses, approval
requests, coverage, drafts), fraud brainstorm and inquiries, internal control and exceptions,
service organizations and SOC reports; matrix actions in `workpapers.yaml` and `assurance.yaml`
(agent and client principals denied every write; reads `task_scope` for the agent); six flags;
status words (DF-31); OpenAPI examples that foot; `make generate`.
**Out**: tables (T03, T06, T25), services (T04, T07, T12, T13, T18, T19, T31), the agent (T11,
T15), the C3 decision kinds, the human-only register entry for `fraud_minutes.approved` (needs a
migration; T19).

## Plan (amber)
1. Tests first: `backend/tests/contracts/a04_planning/test_a04_stub.py` (route family and actions,
   live routes untouched, Idempotency-Key, classification, matrix cells, flags, examples foot,
   gate order).
2. Matrix and flags (`make regenerate`: `_matrix.py`, `actions.gen.ts`, `_flags.py`), status
   vocabulary (`_statuses.py`, `status.gen.ts`).
3. `workpapers/contract.py` and `assurance/planning_contract.py`, mounted after the live routers.
4. `make generate`; check the OpenAPI diff is additive (no schema renamed).
Rollback: revert the commit; no migration, no data.

## Progress log
- `2026-10-31` — built. Model names collided with live schemas (`CellOut`, `RiskOut`,
  `MaterialityOut`…); renamed so the OpenAPI diff is purely additive (47 operations, 0 renamed).
  error-codes.yaml unchanged by this task (the stub raises only 404/501). Tests run at the S22
  end review.
- `2026-10-31` — S22 end review: two optional amounts (`Money | None`) dropped their
  classification tag (now `Annotated[Decimal | None, classified(...)]`); the severity proposal's
  operation id duplicated fieldwork's `propose_severity` (renamed); the flag test compared the
  registry's stored word; `test_app_gates` lists every A-04 POST by its status; the generated
  security tests regenerated. **Made twice:** `Alias | None` on a classified alias loses the tag
  (pydantic keeps metadata only inside `Annotated`); candidate lint.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1757 | A-04 paths that collide with live SPEC-300/308 routes move; flags dated from today | No |
