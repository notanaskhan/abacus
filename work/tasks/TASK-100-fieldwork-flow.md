---
id: TASK-100
title: "SPEC-040: sample approval, one support request per sample, row sign-off (prepared / reviewed) with staleness, workpaper gated on rows, step tracker and triage"
spec: SPEC-040
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12]
risk_zone: red
status: done
branch: spec-040-fieldwork-flow
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Objective
Build SPEC-040 on the fieldwork module (ADR-131, ADR-132).

## Plan
1. **Migration 0061:**
   - `selection_approvals` and `item_signoffs`, insert-only, with RLS forced.
   - Owner grants.
   - `schema_check` entries: INSERT_ONLY_TABLES, APP_INSERT_COLUMNS, TABLE_OWNERS.
2. **Matrix:** `sample.approve`, `item.sign_prepared`, `item.sign_reviewed` (with `agent: deny`); regenerate `_matrix.py`; the `test_independence` list.
3. **Service** (`fieldwork/workpapers.py`, `service.py`):
   - `approve_sample`;
   - an `_approved` gate on `record_result`, `request_support` and the sign-offs (`sample_not_approved`);
   - `request_selection_support` (one request, items linked, `already_requested`);
   - `sign_items(level, item_ids)` with the preparer ≠ reviewer check;
   - row-state reads;
   - `sign_ready` / `sign_reviewed` gated on current row sign-offs.
4. **Routes:**
   - `POST …/procedures/{id}/approve`;
   - `POST …/procedures/{id}/request-support`;
   - `POST …/procedures/{id}/items/sign` (body: level, item_ids);
   - `ProcedureOut` gains `approval` and `steps`; `ItemOut` gains `prepared` / `reviewed` (initials, stale);
   - `make generate`; the `test_app_gates` route list.
5. **Web** (`Fieldwork.tsx`):
   - a step tracker;
   - an "Approve sample" card (manager/partner);
   - "Request support for n items";
   - triage counts;
   - P/R slots per row with select-to-sign;
   - a bulk "Sign selected as preparer / reviewer";
   - "Changed after sign-off".
6. **Tests:** service tests per AC, the matrix, and web screen tests.

Protected paths:
- `docs/architecture/permission-matrix.yaml`
- `backend/migrations/versions/*`
- `backend/src/abacus_tools/quality/schema_check.py`
- `backend/src/abacus/app.py` (only if routes need registering)
- `backend/tests/unit/test_app_gates.py`, `backend/tests/unit/identity/test_independence.py`
- the fieldwork module (red)

## Definition of done
- [x] AC tests pass: `tests/unit/fieldwork/test_flow.py` (7), `spec040flow.test.tsx` (6), web 359.
- [x] `make check-fast` passes.
- [x] The flow walked on the dev stack:
  1. Dana approved a 14-entry journal entry sample.
  2. One client request went out for the 14 entries.
  3. Sam (staff) recorded a result and signed it as preparer, and Dana signed it as reviewer.
  4. Sam changed the result, and the sign-off showed "changed after sign-off".

## Progress log
- 2026-10-20: migration 0061, `flow.py`, gates in `workpapers.py`, routes, matrix, web, tests.

## Gotchas and discoveries
- Request descriptions hold 2,000 characters, so one request lists about 55 items and then says "and n more". SPEC-040 AC-4 was updated to match.
- The generated client already had an onboarding `StepOut`, so the flow's step model is `FlowStepOut`.
- A pre-existing bug, fixed: the procedure pane reused the list's copy of a procedure, which has no selection, so a fresh load showed "No entries selected yet" until a refetch. The detail is now fetched on mount.
- Results recorded before this task, on samples nobody approved, stay (Q2). New results need an approval.
- Owed: ADR-078 integration tests against the database for approve / request / sign, written in the other founder's session.
