# reporting

Zone: amber. Pre-registered by F-03-T08 (ADR-140); first epic P-11 (document services).

Owns (docs/plan/03-backend-architecture.md §2.2): generated documents and render jobs, statement
documents and versions, line items, linked values, tracked changes; the renderer service.

- `contract.py`: C11 v1 (`docs/contracts/c11-renderer.md`): DocBlocks, generated documents,
  field regions, compare, changes, report templates; routes 404 off / 501 on behind
  `reporting.generated_documents` until P-11-T06 and T11 (P-11-T03).
- `templates.py` (P-11-T06): bundle validation by path (markup, unknown variables, unknown
  layout, clause conflicts, size) and the live template routes over `methodology.api`'s storage.
- `api.py`: the in-process renderer API: `register_document_kind`, `check_render_request`,
  `render`, `render_final`, `lock` (P-11-T08 implements).
- `render/`: the deterministic renderer (ADR-320): vendored fonts checked against
  `fonts/MANIFEST.sha256`, a deny-all `asset:` fetcher, WeasyPrint PDF and python-docx DOCX with
  fixed metadata (P-11-T02; T07 and T10 complete it). Imported only inside the isolated child:
  WeasyPrint needs the image's pinned Pango and HarfBuzz.
- `render/` (P-11-T07): `layouts.py` (six code-owned layouts, watermark, legend, consent floor),
  `text.py` (literal text, glyph coverage), `html.py` (DocBlocks to HTML; `missing_variable`),
  `head.py` (no Pango), `core.py` (`build_html`, `render`, `render_isolated`, `engine_version`).
- `fonts/`: Arimo, Gelasio, Geist Mono (OFL 1.1) with their licences.

Byte stability: `make golden-render` (two fresh containers, no network).

Operations (P-11-T17): `docs/runbooks/RB-43-document-services.md` (failed renders and their codes,
engine upgrade and golden re-baseline with both approvals, template rollback by republishing a
prior version). The kill switch is `reporting.generated_documents` (owner ayushkbhatia; expiry in
its flag file). Adding a document kind: `.claude/skills/backend-module/SKILL.md`.

Live since P-11-T08 and T11: `documents.py` (generated documents, versions, sealed snapshots,
events), `render_job.py` (the render job: compose, render isolated, store, record files, or fail
with a code), `files.py` (rendered files as evidence versions and the field-region manifest),
`reads.py` (the live routes: read, versions, fields, compare, changes, regenerate with an
`Idempotency-Key`, template list and SAMPLE preview), `compose.py`, `consent.py` (the §7216 consent
floor), `engagement_letters.py` (C11's `engagement_letter` kind for ENG-04).
