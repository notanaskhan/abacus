---
id: ADR-320
title: Deterministic document generation
status: accepted
date: 2026-10-29
deciders: ayushkbhatia
risk_zone: amber
proposal: P-19
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

P-ID **P-19** (chapter 09 §9.4.2). The plan reserved "ADR-152" for it; that number went to the
unauthenticated operational routes, so P-19 takes ADR-320 from `docs/adr/backlog.md` (P-11-T01,
TASK-2203). Records **DEC-44**; extends **ADR-042** (deterministic spreadsheet rendering).

## Context
Letters, §7216 consents, representation and governance letters, audit and review reports, notice
responses, delivery cover letters, financial-statement packages and run trace exports must be
produced by the platform, stored as evidence, signed through C7 and re-produced years later with
the same bytes. A reviewer approves a specific rendering; an e-signature binds a specific
fingerprint; an inspector compares a filed letter with its source. If the same inputs can yield
different bytes, approvals, signatures and audit trails stop meaning anything.

Constraints: DEC-16 (no headless Chromium, no pdf.js; new runtime dependencies are an allowlisted
batch), DEC-44 (deterministic generation with a fallback), ADR-042 (openpyxl already renders XLSX
deterministically), ADR-110 (server-side page images through pypdfium2 in an isolated child),
AGENTS.md rules 5 and 7 (agents propose, code computes), rule 16 (templates are database content),
and the public repository (no firm content or secrets in git).

## Decision
1. **Engines.** PDF through **WeasyPrint**; DOCX through **python-docx**; XLSX stays openpyxl
   (ADR-042). No headless browser, no client-side rendering, no pdf.js. pdfplumber reads rendered
   word boxes for field regions; pypdfium2 rasterises pages for previews (ADR-110).
2. **One model, code-owned layouts.** Every document is a tree of **DocBlocks** (the closed C11
   vocabulary: section, heading, paragraph runs of text, variable and citation, clause, list, table,
   kv, signature block, legend, image, enclosures, page break) rendered through a code-owned layout
   (`letter`, `consent_7216`, `report`, `notice_response`, `package`, `run_export`). Templates are
   **database rows** in `methodology` (`report_templates`, insert-only versions, human-only
   publication); never constants, never migrations, never model output. No HTML, CSS or markup ever
   comes from a template, a variable or a model: `markup_not_allowed`.
3. **Byte stability is a requirement, tested.** The renderer runs in a digest-pinned
   `worker-batch` image with pinned Pango, HarfBuzz and fontconfig; vendored **Arimo**, **Gelasio**
   and **Geist Mono** with their licences and a SHA-256 fonts manifest; a fontconfig that lists only
   that directory (a missing glyph refuses with `missing_glyph`, never falls back); PDF
   `CreationDate`/`ModDate` from the snapshot's `as_of`; the PDF identifier from the content hash;
   numbers and dates formatted by `reporting/format.py` (the port of F-05's `format.ts`, same golden
   cases); ZIP containers (DOCX) rebuilt with sorted entries and a fixed timestamp. Golden tests
   compare SHA-256 across two fresh containers and in CI (`backend/tests/golden/render/`).
4. **Isolation and no network.** Every render runs in `kernel.isolation.run_isolated` with renderer
   limits; the URL fetcher refuses every scheme; assets resolve from an in-memory map keyed
   `asset:<id>` (fonts, and letterhead or signature images read through `evidence.api`).
5. **Variables are typed and resolved server-side.** Each document kind registers a variables
   provider; values come from the database into a sealed snapshot with its `content_hash`; the
   browser never sends values. Code formats every number; the renderer never sums (rule 7). A
   missing variable refuses with `missing_variable`, never renders blank.
6. **Modes.** `draft` (DRAFT on every page), `sample` (SAMPLE, template previews, never evidence),
   `final` (no watermark) only with a verified human `approval_ref` whose content hash matches. An
   agent may request drafts only (rule 5, INV-1). Versions are insert-only; a regenerate is a new
   version; a locked document is never re-rendered.
7. **Rendered bytes are evidence.** Each file is written through `evidence.api.record_generated`
   in the caller's unit of work, its evidence fingerprint equal to its render hash.
8. **Engine upgrades** change bytes: they need a recorded golden re-baseline, never re-render a
   final or locked version and never mark documents out of date.
9. **OCR is not rendering, and not a model call.** Reading scans (DEC-42) is ADR-321's: Amazon
   Textract is a document service, not a model call under AGENTS.md rule 6, gated in code by the
   kill switch, the firm flag, the provider-terms register and the §7216 rule, and never used by
   the renderer. Nothing in `reporting` calls a model or Textract.
10. **Fallback.** If the P-11-T02 spike cannot make WeasyPrint byte-stable across two containers
    by its timebox, the renderer moves to **Typst** behind the same C11 shapes (engine-agnostic),
    and that switch is recorded as a superseding ADR.

## Options considered
### Option A: WeasyPrint + python-docx in a pinned image, DocBlocks, goldens — chosen
- Pros: pure Python in the existing worker; HTML/CSS layouts match the handoff paper CSS; no
  browser attack surface; DOCX from the same model; byte stability testable.
- Cons: system-library pinning (Pango, HarfBuzz) and font subsetting must be held still; field
  rects need a word-box refinement.

### Option B: Headless Chromium print-to-PDF
- Pros: highest CSS fidelity.
- Cons: banned by DEC-16; a browser with network stack in the renderer; bytes vary across builds.
- Why rejected: DEC-16 and the isolation rule.

### Option C: Typst
- Pros: deterministic by design; fast.
- Cons: a second layout language; no DOCX; a new toolchain in the image.
- Why rejected: kept as the recorded fallback (decision 10), not the default.

### Option D: Render on the client (pdf.js / browser)
- Why rejected: DEC-16; the bytes are evidence and must be produced server-side.

## Consequences
**Positive**
- An approval, an e-signature and an evidence fingerprint all name the same bytes.
- Templates are firm content in the database, edited and published by people.
- One DocBlock model serves PDF, DOCX and the T10 `DocumentVM` (F-06).

**Negative / costs accepted**
- The worker image is digest-pinned and its upgrades need a golden re-baseline.
- Three runtime dependencies join the allowlist through the DEC-16 batch (WeasyPrint,
  python-docx, pillow-heif for ADR-321).

**Follow-up work created**
- P-11-T02 (toolchain and byte-stability spike), T03 (C11 stub), T05 (`reporting_v1`), T06
  (templates), T07 (renderer core), T08 (RenderWorkflow), T09 (`record_generated`), T10 (DOCX),
  T12 (goldens), T14 (independent tests).

## Enforcement
- [x] Test: `backend/tests/golden/render/` SHA-256 goldens across two containers (P-11-T02, T12).
- [x] Test: the C11 consumer suite `backend/tests/contracts/c11_renderer/` (P-11-T04): refusal
      codes, human-only final and regenerate.
- [x] Architecture / dependency rule in CI: `dependency-allowlist.yaml` (WeasyPrint, python-docx
      only in `reporting`); banned-patterns keep `dangerouslySetInnerHTML` and raw HTML out.
- [x] Hook or protected path: `backend/tests/golden/render/*.sha256` change only with a recorded
      re-baseline reason.
- [ ] Reviewer agent checklist item: architecture reviewer checks "no network in render".

## Guidance for agents
Never build a document from a string template, an f-string or model text. Add a document kind by
registering it with `reporting.api.register_document_kind`, put its wording in a database template,
and let the renderer resolve typed variables. If a render's bytes change without an input change,
that is a defect: fix the pinning, never the golden.
