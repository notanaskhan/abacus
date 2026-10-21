---
id: SPEC-315
title: "Source pointers: values point back to where they were printed (hover snippet, click to the outlined line or cell)"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-110, ADR-052, ADR-065]
related_specs: [SPEC-029, SPEC-308, SPEC-312]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
A value read from a document points back to where it was printed. Hovering or focusing it shows a snippet of the source:
- for a PDF, the page cropped around the outlined line;
- for a spreadsheet, the cell among its neighbours.

Clicking opens the source viewer at that spot, outlined or highlighted. Boxes come from the server's extraction; the browser never reads the document.

## 2. Acceptance criteria
- **AC-1 Positions.**
  - Extraction v3 keeps each PDF text line (pdfplumber) with its box as fractions of the page: x0, top, x1, bottom.
  - Earlier extractions and PDFium-read pages have no boxes, and pointers to them fall back to the page.
- **AC-2 Statements.**
  - Statement lines read from PDFs keep their page and box.
  - The summary values (opening, closing, period, last 4) keep the page and box of the line that printed them.
  - Approval stores both: `statement_transactions.box` and `statement_datasets.field_sources` (migration 0078, nullable, still insert-only).
- **AC-3 Previews.**
  - PDF previews carry each page's lines and boxes (`page_lines`).
  - `GET /v1/engagements/{id}/evidence-versions/{version}/preview` and `/preview/pages/{n}` (`evidence.read`, through a request item the version fulfils, or on the engagement for a version no item holds) open a version without naming its request.
- **AC-4 Viewer.** The source viewer outlines the given boxes (or a quote found among the page's lines), opens at the page and scrolls the outline into view. Cell citations highlight as before.
- **AC-5 Where it's used.**
  - Statement transaction lines and the printed opening and closing balances.
  - Screening citation values (cells).
  - Working-paper cell citations, which open at "page N" from the typed locator. This closes the gap where they couldn't open their document.

## 3. Out of scope
- Trial balance lines pointing back to the imported file's rows (needs the import's source references mapped to cells).
- Re-extracting older uploads to add boxes.
- Boxes for PDFium-read and OCR'd pages (P-32).
- Highlighting a box for agent PDF quotes in AI review (the viewer supports `findText`; AI review doesn't pass it yet).
