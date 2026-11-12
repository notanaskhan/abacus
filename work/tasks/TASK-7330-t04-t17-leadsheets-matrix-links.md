---
id: TASK-7330
title: "T-04-T17 rest: live leadsheets, Sch E K-1 matrix with the PY column, region-field-line links, and the code mismatch check"
spec: SPEC-649
acceptance_criteria: [AC-1, AC-2]  # AC-1.1/1.2 cards and links; AC-1.4 mismatch; AC-2.3 matrix
risk_zone: amber
status: in-review
branch: s36g-t04-t29-gaps
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T17
---

## Objective
T-04-T17 (S34, TASK-6616) left three RW-1 routes answering 501: `GET …/leadsheets`,
`GET …/matrices/sch-e-k1` and `GET …/links`. Its note said they waited on "the engine's
document-to-field map, T-04-T21"; T-04-T21 is TAX-05's fixture screen, and no static map is needed.
A field's link to a document is its latest value version's citations (`field_value_versions.
citation_ids`, verified `document_text` claims with a page and a box, T-04-T14's `box_claim`).

## Plan (amber)
- `evidence`: `citation_boxes(tenant, engagement_id, citation_ids)` in `screening_facts.py` over a
  repository read: verified, shown (no shadow, source not withdrawn), never moved or broken,
  `document_text` on an evidence version, with a page and a 4-number box. Exported in `api.py`.
- `review`: `latest_citations(tenant, target_type, target_ids)` in `field_values.py`, the latest
  version's citation ids per field. Exported in `api.py`.
- `tax/compute/individual/k1.py`: `sch_e_matrix` (pure, stamped): the K-1's amount lines with the
  PY figure by field key (T-04-T11's missing "Sch E K-1 matrix").
- `tax/leadsheets.py` (new service):
  - leadsheets: the form's worksheets, one card per section, a line per `line_ref`
    (`{form}.{line_ref}`), the amount summed by `leadsheet_line`, the contributing field keys, and
    `mismatch` when a cited box's value differs from the field's value.
  - matrix: each K-1 activity's worksheet amount lines, the PY figure from the prior-year return's
    activity for the same issuer (the SALY join), the activity status.
  - links: every live box citation of the return's fields, optionally one evidence version.
  - Reads authorise `return_worksheet.read` on the engagement (404 for a client or a wall).
- `tax/workspace_contract.py`: the three routes call the service; `errors=(501,)` stays declared
  (the RW-1 consumer test pins it).
- Docs: `docs/contracts/tax-review-workspace.md`. No migration, no flag, no new route.
- Rollback: revert the PR; the routes answer 501 again.

## Tests
- `tests/unit/tax/test_t04t17_leadsheets_matrix_links.py` (13): the matrix compute; line sums,
  the mismatch flag, the links' locators and the evidence-version filter, a field whose box is not
  live has no link, the PY gate, 404 for a client and an unknown return year (fake session).
- `tests/integration/test_t04t17_leadsheets_matrix_links.py`: the leadsheet, activity,
  prior-year and K-1 amount queries on Postgres (form, active, line and amount filters; order; the
  SALY join by issuer and year). `citation_boxes_among`'s filters copy `supported_citations_among`
  and are not exercised on Postgres here.

## Built (DEC-4330)
- As planned. `FieldLink` (not `Link`: the glossary bans "link" as a code name, L12).
- The matrix's text rows on the artboard (entity type, TSJ, passive/nonpassive) are not amounts:
  `K1MatrixRowOut` carries money only, so they stay with TXI-02 (T-04-T40).
- No OpenAPI change (the shapes were the stub's); the RW-1 consumer suite passes (37).

## The code mismatch check (AC-1.4; added on Ayush's "Yes, build it")
- `tax/leadsheets.py`: `mismatched_documents`: each document version whose cited box printed a
  figure other than its field, with the first such field's key (`LINKED_FIELDS` now reads
  `current_value`).
- `tax/review_tree.py`: the tree's document reads `mismatch` with `mismatch_field_key` (unless it
  is already approved at the level); `approve` raises `Mismatch` (409 `mismatch`,
  `facts.field_key`) after the version check and before the unit of work. A key over 64
  characters (the facts limit) is left out of the facts rather than turning the 409 into a 500.
- `workspace_contract.py`: `ReviewDocumentOut.mismatch_field_key` filled (the field was the
  stub's).
- Web `TAX-04/live-core.ts`: a 409 `mismatch` reads "Resolve 1 mismatch to approve" (the generic
  sentence before). The disabled Approve and the helper were already built (TASK-6828).
- Tests: four more unit cases (the documents named, the tree state, approved stays approved, the
  409 writes nothing, a long key) and one vitest case; `test_t04t29_unapprove_and_request.py`'s
  wiring gets a no-mismatch stub for the new collaborator (no assertion changed). The Postgres
  test reads `LINKED_FIELDS` too.
- `review_tree`'s error classes are not in `docs/architecture/error-codes.yaml` (the app imports
  the module lazily, so the catalogue gate does not see them); `version_superseded` is the same.

## Partial
- The staging walk (no staging).

## Progress log
- `2026-11-12` — Plan written (S36 session, on Ayush's "Yes, build it").
- `2026-11-12` — Built. ruff, pyright (changed files), lint-imports, banned_patterns,
  validate_docs, register_ids green; unit 13 + T11 compute pass; RW-1 contracts 37 pass. The
  Postgres test waits on the shared test lock (S38's end pass holds it).
- `2026-11-12` — Under the test lock: `tests/integration/test_t04t17_leadsheets_matrix_links.py`
  passes on Postgres (1 test, 12 s).
- `2026-11-12` — The code mismatch check added. ruff, pyright (changed files), lint-imports,
  banned_patterns, validate_docs, register_ids, error_codes green; tax review-tree unit tests 36
  pass; TAX-04 vitest 23 pass; web tsc, eslint, prettier clean. The extended Postgres test waits
  on the test lock (S38 holds it).
- `2026-11-12` — Under the test lock: the extended Postgres test (with `LINKED_FIELDS`) passes
  (1 test, 13 s).
