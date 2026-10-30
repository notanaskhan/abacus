---
id: TASK-2304
title: P-11-T07 renderer core
spec: SPEC-520
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-28]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T07
branch: s18-p11-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
DocBlock to HTML through code-owned layouts (letter, consent_7216, report, notice_response,
package, run_export; flow and fixed) with the handoff paper CSS; WeasyPrint in the isolated child
with the deny-all fetcher and in-memory assets; fixed metadata and document ID; DRAFT and SAMPLE
watermark; per-page legend; consent minimum type size; C11 v1 frozen. Acceptance (row): hostile
variable text renders as literal text, no URL is ever fetched, every draft page carries the
watermark, the golden letter is byte-identical on rerun, and the C11 v1 OpenAPI snapshot is
frozen.

## Plan
- `render/text.py`, `render/layouts.py`, `render/html.py`, `render/core.py`; `render/head.py`
  split from `pdf.py` so HTML builds without Pango; `render_pdf` takes extra assets.
- C11 v1 frozen through `abacus_tools.contracts` (`c11_renderer/v1.json`).
- Tests: `tests/unit/reporting/test_p11t07_renderer_core.py` (no Pango) and
  `tests/golden_render/test_p11t07_render_core.py` (image: bytes, watermark per page, hostile text,
  fetcher, legend per page).
- Not here: RenderWorkflow, snapshots and versions (T08), DOCX from DocBlocks (T10), the SAMPLE
  preview route (T11).
- Rollback: revert.

## Per AC
| AC | Evidence |
|---|---|
| AC-6 | golden_render `test_ac6_*` (same input, same bytes, three pages) |
| AC-7 | unit + golden_render `test_ac7_*` (DRAFT every page, SAMPLE, none on final) |
| AC-8 | unit `test_ac8_*`, golden_render `test_ac8_*` |
| AC-9 | golden_render fetcher and image tests; unit image `asset:` test |
| AC-10 | unit `test_ac10_*` |
| AC-11 | unit + golden_render `test_ac11_*` |
| AC-12 | unit `test_ac12_*` |
| AC-28 | `tests/contracts/c11_renderer/v1.json`; unit `test_ac28_*` |

## Progress log
- `2026-10-30` — built (DEC-1351). Tests written, not yet run (S18 end review; golden_render needs `make golden-render`).

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-01-T17 consent templates on the `consent_7216` layout.
