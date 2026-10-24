---
id: TASK-1042
title: C5 section portal-pbc contract stub for POR-03, POR-04 and POR-14 (R-01-T01)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: red
status: done
epic: R-01
plan_key: R-01-T01
branch: s7-r01-portal-requests
created: 2026-10-24
updated: 2026-10-24
---

Plan of record: R-01 (docs/plan/epics/R-01.md §3.1–§3.6, §4.3–§4.8).

## Objective
"The stub merges dark with generated client types, all three flags off and a contract doc naming
every human-only action and audit event." Contract first (AGENTS 15): the models, routes, matrix
row, flags, generated client and `docs/contracts/portal-pbc.md` for the POR-03/04/14 family, so
R-01-T02 (consumer tests), T05 (fixtures) and T06 (POR-03 part 1) build on generated types.

## Plan (red: contract stub only; no migration, no service logic)
- **Files (new):** `backend/src/abacus/modules/portal/pbc_contract.py` (binder picker, binder,
  request, room, suggest, drop poll), `requests/pbc_contract.py` (ignore undo, mark-done undo, the
  firm's void of a rule fulfilment), `evidence/drops_contract.py` (the drop),
  `backend/tests/contracts/c5_portal_pbc/test_c5_portal_pbc_stub.py`,
  `docs/contracts/portal-pbc.md`.
- **Edits:** each module's `api.py` mounts its router; `identity/routing.py` gains 413 and 415 as
  declarable errors; `permission-matrix/portal.yaml` gains `portal_documents.read`;
  `feature-flags/portal.yaml` gains `portal.documents_v2`, `portal.drop_sort`,
  `portal.third_party_room` (boolean, default off, expiring 2027-04-21 under DEC-137); `docs/contracts/README.md` C5 row;
  decision DEC-240. `make regenerate` (matrix, flags, security tests, OpenAPI, client).
- **Stub behaviour:** flag off 404; flag on 501 `not_implemented` until T07, T08, T09, T13.
- **Tests:** each route's one action and its 404/501 answers; 409 on the undos and the void;
  202/413/415 and `X-Drop-Batch` on the drop; `Idempotency-Key` on every client-facing write;
  every field classified; the read action grants client roles only, `scope_only`, agent and
  system denied; the void human only; flags boolean and off.
- **Rollback:** revert the commit (no data, no migration; flags off).

## Decisions (DEC-240)
- `portal.documents.read` is spelt `portal_documents.read` (DEC-139).
- The check of the `third_party` `delegated_only` rows: neither the role nor the condition exists
  in the matrix grammar; R-01-T13 adds both with the room read model. Until then no third party
  reaches any route.
- Return reasons on the portal projection: `wrong_year`, `wrong_period`, `other` (P-06's return
  carries none; T07 maps).
- The undo answers carry client words (`client_status`, the Mark as Done state), never the C2 firm
  code, so the section is clean for R-01-T02's no-firm-status rule.

## Progress log
- 2026-10-24: stub, matrix row, flags, contract doc and DEC-240 written; `make regenerate`.
  Checks: `pytest tests/contracts/c5_portal_pbc` (59 passed), ruff, pyright; the unit, contracts
  and security suites (see below).
