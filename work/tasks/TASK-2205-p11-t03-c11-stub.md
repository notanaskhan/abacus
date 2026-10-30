---
id: TASK-2205
title: P-11-T03 C11 stub (DocBlocks, RenderRequest, GeneratedDocumentOut, FieldRegion, templates)
spec: SPEC-520
acceptance_criteria: [AC-31]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T03
branch: s17-p11-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The C11 v1 stub: models with classification tags, fixture-returning routes, matrix rows, the
`reporting.generated_documents` flag, `make generate`.

Acceptance: "The generated client exposes every C11 route returning seed-derived fixtures, each
route declares one matrix action, and agent principals are refused final renders, regeneration and
template publication."

## Plan (amber)
Files: `backend/src/abacus/modules/reporting/contract.py` (Pydantic models: DocBlock union,
RenderRequest, RenderTicket, GeneratedDocumentOut and versions, FieldRegionOut, ReportTemplateOut,
ImportReport; routes as `docs/contracts/c11-renderer.md` §2, 404 with the flag off); `api.py`
(ROUTERS, `register_document_kind` signature stub, the in-process shapes); the matrix
(`docs/architecture/permission-matrix.yaml` reporting section: `generated_document.read`,
`generated_document.regenerate`, `report_template.read`, `report_template.import`,
`report_template.publish`) then `make regenerate`; `docs/architecture/feature-flags.yaml`
(`reporting.generated_documents`, per firm, default off, owner, expiry); fixtures from the
Brightwater Hale seed (the Copperleaf engagement letter); the C7-style stub test of every route;
`make generate` for `packages/api-client`. Rollback: revert; the flag is off everywhere.

## Progress log
- `2026-10-29` — Planned in P-11-T01.
- `2026-10-29` — Built on `s17-p11-t03` (stacked on T02): `reporting/contract.py` (DocBlock union,
  generated documents, fields, compare, changes, ticket, templates, import, preview; ten routes),
  `reporting/api.py` (ROUTERS, in-process shapes, `register_document_kind`,
  `check_render_request`), matrix and flag files, `make regenerate` (flags, matrix, OpenAPI, api
  client, actions), fixture handlers, `tests/contracts/c11_renderer/test_c11_stubs.py`,
  `reporting` marked landed in the pre-registration test, C11 doc and README. Tests run at the
  S17 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1253: 404/501 stub rule; seed fixtures in fixture mode; final render in-process only | the repo's stub convention; a backend stub never returns invented data | no |
