---
id: SPEC-029
title: "Upload processing: scanning, extraction, mechanical checks and preview"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-016, ADR-017, ADR-031, ADR-042, ADR-050, ADR-052, ADR-064, ADR-090, ADR-110, ADR-111]
related_specs: [SPEC-020, SPEC-021, SPEC-023, SPEC-028]
created: 2026-10-12
updated: 2026-10-12
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Every uploaded file is **scanned for malware, then processed in isolation**: its text, tables, dates, entity names and totals are extracted into a derived record, and **mechanical checks** run on it by code. A client learns within seconds, in fixed words, that a bank statement is for the wrong month, the wrong company, unreadable or a duplicate, and can replace it before the firm looks. The firm sees the same results on the item, plus **ledger cross-checks** (statement closing balance against the cash account, aging total against its control account).

Both sides can **preview** evidence in the browser from server-made page images and extracted values, so review never needs a download. This is Track A5 and A4's preview; its extraction is what B3 (matching) and B4 (upload reviewer) build on.

## 2. Problem and context
- **Uploads aren't scanned.** SPEC-020 uploads and SPEC-023 inbox files are stored and offered for download as they arrive. ADR-110 requires a scan before any parsing; TASK-052 added `kernel.scanning` for ledger imports only.
- **Nothing reads an upload.** A bank statement for November instead of December, or for a sister company, is found only when someone on the team opens it, days later.
- **Review means downloading.** Item detail offers "Download" only; a reviewer opens each file locally.
- **Requests don't say what kind of document they expect.** A request item has a description, an audit area, a tier and a dataset (SPEC-022), but nothing says "bank statement" or "aging schedule", so no check knows what to look for.
- **The ledger is there.** Tier A trial balances are retrieved or imported (SPEC-028) and snapshotted, so a document's totals can be compared with the books by code (ADR-050).
- `pdfplumber` is on the dependency allowlist as *pending* ("decide when scanned evidence arrives").

## 3. Actors
| Actor | Role here |
|---|---|
| Client admin and contributor | Upload files; see document problems at once in plain words; replace a file |
| Engagement partner, manager, senior, staff, reviewer | See checks and cross-checks on the item; preview evidence without downloading |
| The platform (code) | Scans, extracts in isolation, checks, renders previews, records results |

## 4. Goals and non-goals
**Goals**
1. **Scan every upload** (SPEC-020 item uploads, SPEC-023 inbox files) with `kernel.scanning` before it's stored as evidence. A refused file is never stored, parsed or previewed, and the uploader sees a fixed message.
2. **Process each stored upload in a Temporal workflow** (`upload_processing`, one per evidence version or inbox file, ADR-017, ADR-090): extract, check, render previews, record. Each parse runs in a short-lived child process with time, memory, size and page limits, as TASK-052 does for imports.
3. **Extraction** (a derived record, ADR-110; never alters evidence; rebuildable):
   - **PDF** (text layer): page text, simple tables, dates, amounts, entity names, and for a bank statement: account holder, last four digits of the account, statement period, opening and closing balance, total credits and debits when printed;
   - **XLSX and CSV**: cached cell values only (formulas never evaluated), sheet names, header rows, total rows; for an aging schedule: as-of date, bucket columns, row totals, grand total;
   - **Scanned PDFs** (no text layer) and **encrypted PDFs**: `unreadable`, with guidance (ADR-110);
   - **Images, Word documents**: stored and previewed (images only), not extracted (non-goal).
4. **Document kinds on request items**: `bank_statement`, `aging_schedule`, `schedule` (any other spreadsheet schedule), or none. Set by code rule from the description when an item is created or classified (as tier rules do, SPEC-022), carried by methodology template items, and editable by the team (Q4).
5. **Mechanical checks** (code only, ADR-050), each with an outcome `passed`, `problem` or `not_applicable`, a fixed code, and only code-computed values:
   - **all files:** `unreadable`; `duplicate` (the same fingerprint already on this engagement, any item);
   - **bank statement:** `wrong_period` (the statement period doesn't include the engagement's year end), `stale_as_of` (the period ends more than 45 days before the year end), `wrong_entity` (the account holder doesn't match the client entity's name after normalisation), `totals_dont_add_up` (opening + credits − debits ≠ closing, when all four are printed);
   - **aging schedule:** `wrong_period` (as-of date isn't the year end), `totals_dont_add_up` (bucket columns don't sum to each row's total, or rows don't sum to the grand total);
   - **schedule:** `totals_dont_add_up` (a labelled total row differs from the sum of the column above it).
6. **Ledger cross-checks** (firm side only, Q3), against the engagement's latest succeeded trial balance snapshot for the year end:
   - bank statement closing balance against the cash account it maps to (Q5), reporting the difference;
   - aging schedule grand total against the receivables (or payables) control account, reporting the difference.
7. **Results:**
   - the **client** sees document problems on their upload within seconds, in fixed words (ADR-111), with "Replace file"; ledger cross-checks and judgement are never shown to clients;
   - the **firm** sees every check and cross-check on the item and on each version in item detail, and the Board shows a "Problems found" marker.
8. **Preview** (ADR-110: the browser never renders the raw file):
   - PDF: server-rendered page images (PNG, first 50 pages, fixed resolution);
   - XLSX and CSV: the extracted cached values as a table (first 1,000 rows per sheet);
   - PNG and JPEG: re-encoded server-side, metadata stripped;
   - Word documents: "Preview isn't available; download instead".
   Previews are derived objects in storage, made by the workflow, served only to people allowed `evidence.read` on the engagement (client roles: their own uploads, as today).
9. **Flag** `uploads.processing` (off by default; on for the local Dev firm). With it off, scanning still applies (goal 1) and nothing else changes.

**Non-goals**
- OCR for scanned PDFs (chosen with staging, ADR-110).
- Extraction from Word documents and images.
- Model-based reading of any kind: matching an upload to a request (B3) and judgement flags such as "looks altered" (B4) come later and build on this extraction.
- Blocking an upload because a check found a problem: the file is kept as a version (ADR-004), and the client chooses to replace it.
- Processing files uploaded before this ships (Q7).
- Bank-specific statement templates: extraction uses general labels ("Statement period", "Ending balance", …), checked against synthetic statements in several layouts.

## 5. User stories and acceptance criteria
**Story 1 — a client finds out at once.** Rachel uploads November's bank statement to "Bank statement for December". Seconds later the item says "This statement ends on November 30, 2026; we need one that includes December 31, 2026", and she replaces it.

**Story 2 — the firm sees what code found.** Maya opens the item: the statement passed every document check, and the cross-check shows the closing balance is $4,210.00 above the cash account in the trial balance (outstanding checks, to reconcile). She previews the statement page by page without downloading.

- **AC-1** Given any upload (item upload or inbox file), then it's malware-scanned before it's stored as evidence; a refused file isn't stored, and the uploader sees "We couldn't accept this file" with an audit event and no file content logged.
- **AC-2** Given a stored upload with processing on, then an `upload_processing` workflow runs for it, extraction runs in an isolated child process with limits, and a crash, timeout or limit hit records `unreadable`, never a worker failure.
- **AC-3** Given a scanned or encrypted PDF, then the result is `unreadable` with guidance to upload the bank's digital statement.
- **AC-4** Given a spreadsheet with formulas or macros, then only cached values are read; formulas are never evaluated and macros never run.
- **AC-5** Given a request item, then it has a document kind set by rule from its description (or its template), and the team can change it; the change is audited.
- **AC-6** Given a bank statement upload, then `wrong_period`, `stale_as_of`, `wrong_entity` and `totals_dont_add_up` are each checked by code, with outcome and values recorded.
- **AC-7** Given an aging schedule or schedule upload, then `wrong_period` (aging only) and `totals_dont_add_up` are checked by code.
- **AC-8** Given the same file uploaded twice to an engagement, then the second has `duplicate` naming the first item.
- **AC-9** Given a bank statement or aging schedule and a succeeded trial balance snapshot for the year end, then the ledger cross-check records the difference against the mapped account; the client never sees it.
- **AC-10** Given a problem on a client's upload, then the client sees a fixed message within the item, with "Replace file"; no model text, no cross-check and no firm-only check reaches the client (ADR-111).
- **AC-11** Given an evidence version, then the firm sees every check and cross-check in item detail, and the Board marks items with problems.
- **AC-12** Given a PDF, spreadsheet or image, then item detail previews it from server-made images or extracted values, for both client (their own uploads) and firm; the raw file is never rendered by the browser.
- **AC-13** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Design notes
**Data** (evidence module; insert-only, immutable, tenant-scoped):
- `upload_extractions`: one per evidence version or inbox file and extractor version; status (`extracted`, `unreadable`), the derived JSON in object storage (key, fingerprint, size), and summary fields used by checks (document dates, detected entity name, amounts as `numeric`).
- `upload_checks`: one row per check per extraction: check code, outcome, audience (`client` or `firm`), and code-computed values (dates, amounts, an item reference).
- `upload_previews`: per version, page count and object keys of the rendered pages or table JSON.
- `request_items.document_kind` (requests module), set by rule and editable (`request_item.update`).

**Workflow** `upload_processing` (versioned, ADR-090): `scan` (inbox and item uploads already scanned at receipt; the workflow records the result) → `extract` (child process) → `check` → `cross_check` → `preview` → `record` → emit `upload_checks.recorded` for notifications and, later, B3 and B4.

**API** (evidence routes; actions in the matrix): `GET …/evidence-versions/{id}/checks`, `GET …/evidence-versions/{id}/preview` (page list) and `GET …/preview/pages/{n}` (image), `GET …/inbox/{file_id}/checks`. Client uploads show their checks through the existing uploads list.

**Messages** (fixed templates, web): one per check code, filled only with code-computed dates and amounts.

## 7. Security and privacy
- Extracted text, tables and previews are client data: `restricted` classification, never logged, encrypted at rest as evidence is.
- Every string from a file is untrusted (ADR-052, ADR-064): extracted text is displayed as text only; spreadsheet cells starting with `=`, `+`, `-` or `@` are shown as text, never as formulas.
- Limits: 25 MB per file (as today), 200 PDF pages extracted, 50 previewed, 60,000 spreadsheet rows, 30 s per parse, 1 GB memory; archive bombs are refused by the scanner.
- Outside synthetic environments, with no scanner configured, uploads fail closed (TASK-052 behaviour), so staging needs a scanner chosen (TASK-014).

## 8. Delivery (tasks)
- **TASK-054 (red, backend):** scanning for every upload; the `upload_processing` workflow; isolated extraction (PDF, XLSX, CSV); `upload_extractions`; synthetic bank statement PDFs and aging schedules in several layouts (`abacus_tools.synthetic`).
- **TASK-055 (red, backend):** document kinds; mechanical checks; ledger cross-checks; `upload_checks`; the checks API.
- **TASK-056 (amber, backend and web):** previews and the viewer in item detail.
- **TASK-057 (amber, web):** the client's instant results with "Replace file"; the firm's checks in item detail and the Board marker.

## 9. Test plan
| AC | Level | What |
|---|---|---|
| AC-1 | unit, integration | EICAR and archive bombs refused for item and inbox uploads; nothing stored; audit event |
| AC-2, AC-3, AC-4 | unit, workflow replay | Child-process limits; scanned and encrypted PDFs; formulas and macros; replay histories |
| AC-5 | unit, integration | Description rules; template carry-over; team override audited |
| AC-6, AC-7, AC-8 | unit | Synthetic statements and schedules: each check's pass and problem, values computed by code |
| AC-9 | integration | Cross-checks against a snapshot; never in client responses |
| AC-10, AC-11, AC-13 | vitest | Client messages and replace; firm view; Board marker; states |
| AC-12 | integration, vitest | Preview objects; access by role; viewer |

## 10. Open questions
All resolved: the founder approved every recommendation below on 2026-10-12.
- **Q1 — PDF library.** Recommended: approve `pdfplumber` (MIT) for text and tables, with its dependency `pypdfium2` (Apache-2.0/BSD) for page images. Not PyMuPDF (AGPL).
- **Q2 — when "before submission" happens.** Recommended: an upload is stored as a version at once (nothing lost, ADR-004) and checked within seconds; the client sees problems on the item and can replace the file. The item still moves to "received" as today. Alternative: a two-step "check, then submit", which holds files outside the evidence record until submitted.
- **Q3 — who sees ledger cross-checks.** Recommended: firm only. A bank-to-books difference is often legitimate (outstanding checks, deposits in transit), so showing it to clients as a problem would mislead.
- **Q4 — document kinds.** Recommended: three kinds now (`bank_statement`, `aging_schedule`, `schedule`), set by description rules and template items, editable by partner, manager and senior. More kinds (loan statements, invoices) come with B3 and B4.
- **Q5 — mapping a statement to a cash account.** Recommended: match the statement's last four account digits to a cash account whose name contains them; otherwise, if the trial balance has exactly one cash account (by the methodology's account ranges), use it; otherwise record `not_applicable` ("Couldn't tell which cash account this statement is for") rather than guess.
- **Q6 — stale tolerance.** Recommended: 45 days before the year end for `stale_as_of`; a firm setting later if firms ask.
- **Q7 — files already uploaded.** Recommended: not processed automatically; their item detail says checks weren't run. Local data only today.
- **Q8 — inbox files.** Recommended: scanned, extracted and previewed on arrival (so B3 can match them later); item-specific checks run when the file is assigned to an item.
