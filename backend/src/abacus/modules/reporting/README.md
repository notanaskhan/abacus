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
