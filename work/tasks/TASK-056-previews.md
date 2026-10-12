---
id: TASK-056
title: "Upload processing, part 3: in-browser previews"
spec: SPEC-029
acceptance_criteria: [AC-12, AC-13]
risk_zone: red
status: awaiting-approval
branch: task-056-previews
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-029 goal 8 and AC-12: the firm and the client can look at evidence in the browser without downloading it. The server makes the preview (page images for PDFs, re-encoded images, extracted values for spreadsheets); the browser never renders the raw file (ADR-110).

## Scope
SPEC-029 AC-12, AC-13 (for the viewer); goal 8.

## Context to load
- Spec: `docs/specs/SPEC-029-upload-processing.md` §4.8, §6, §7; ADR-110
- Code: `evidence/workflows.py`, `processing.py`, `activities.py`, `extraction.py` (TASK-054/055); `kernel/isolation.py`; `evidence/storage.py`; `evidence/item_detail.py` and `routes.py` (download, version access); `apps/web/src/screens/ItemDetail.tsx`, `ClientEngagement.tsx`

## Plan
- [ ] Plan approved by human

### What the code shows
- Item detail offers "Download" only. Client uploads are listed per item with no way to look at one.
- TASK-054's extraction already holds a spreadsheet's cached values (first 60,000 rows) as a JSON object in storage, so spreadsheet previews need no new parse.
- `pypdfium2` and `pillow` are approved (SPEC-029 Q1); neither is used yet. Both are native code reading hostile files, so they run in the isolated child.
- Only uploads (item uploads, inbox files) are processed; versions made by the pipeline (retrieved or imported trial balance workbooks) aren't.

### Design (for founder review)
1. **Workflow v3:** `UploadProcessing` adds `upload.preview` after the checks, behind `workflow.patched("previews")`, for evidence versions and inbox files. A v3 history is recorded; v1 and v2 still replay.
2. **Rendering** (`evidence/previews.py`, in the isolated child):
   - **PDF:** pages rendered with pypdfium2 to PNG, at most 50 pages, scaled to 1,240 px wide (about 150 dpi for a letter page);
   - **PNG, JPEG:** decoded and re-encoded as PNG with Pillow, metadata stripped, at most 2,400 px on the longer side; refuses images over 40 megapixels (decompression bombs);
   - **XLSX, CSV:** nothing rendered; the preview API serves the extraction's tables (first 1,000 rows per sheet);
   - **Word, legacy files, unreadable PDFs:** `none` with a reason ("Preview isn't available; download instead").
3. **Record** `upload_previews` (evidence; migration 0045; insert-only): per evidence version or inbox file, kind (`pages`, `image`, `table`, `none`), page count, reason; and `upload_preview_pages`: page number, storage key, version, fingerprint, size, width, height (content-addressed PNGs).
4. **API** (evidence routes; `evidence.read` on the item with its client facts, as uploads are read; the inbox's own access rule for inbox files):
   - `GET …/request-items/{item}/uploads/{version}/preview`: kind, page count, reason, and for tables the sheets' rows as text;
   - `GET …/request-items/{item}/uploads/{version}/preview/pages/{n}`: the PNG, with `Content-Type: image/png`, `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`; reading a page is not audited (the download is), but each page fetch is authorised;
   - `GET …/inbox/{file}/preview` and `…/preview/pages/{n}` for inbox files.
5. **Viewer** (`apps/web/src/screens/EvidencePreview.tsx`): pages as `<img>` from the page route (lazy, with page numbers), images the same way, tables as a scrollable table with a sticky header where every cell is plain text (a cell starting with `=`, `+`, `-` or `@` is shown as text, never as a formula); loading, empty ("not ready yet" while the workflow runs), error and not-allowed states; colours from tokens.
   - **Firm:** a "Preview" panel beside each version in item detail;
   - **Client:** a "Preview" button on each of their uploads, opening a dialog.
6. **Tests:** rendering per type (synthetic PDFs, an image with metadata, a decompression bomb), limits, isolation; preview records; the API's access rules (a client can't preview another contributor's item, nor any firm-only content); v3 replay; vitest for the viewer's states and plain-text cells.

### Questions for the human
- **D1 — pipeline workbooks.** Recommended: also preview evidence made by the pipeline (retrieved and imported trial balance workbooks), by starting `upload_processing` for every new evidence version, not only uploads; checks still run only where the item has a document kind. Alternative: uploads only, and the firm downloads workbooks as today.
- **D2 — page images or text only.** Recommended: page images (what the reviewer actually sees, including stamps and signatures). Alternative: extracted text only, which is smaller but loses layout.
- **D3 — limits.** Recommended: 50 pages, 1,240 px wide, 1,000 spreadsheet rows per sheet in the viewer, as SPEC-029 §7 says; "Download" stays for anything longer.
- **D4 — approval file:** `backend/src/abacus/modules/evidence/**`, `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py` (if the list exemptions need entries), `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after TASK-054 (#100) and TASK-055 (#101) merged.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
