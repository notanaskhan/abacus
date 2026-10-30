---
id: ADR-321
title: OCR and document understanding
status: accepted
date: 2026-10-29
deciders: ayushkbhatia
risk_zone: amber
proposal: P-32
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

P-ID **P-32** (chapter 09 §9.4.2). The plan reserved "ADR-153" for it; that number went to the
malware-scanning service, so P-32 takes ADR-321 from `docs/adr/backlog.md` (P-11-T01, TASK-2203).
Records **DEC-42**; follows **ADR-110** (server-side page images and the word layer) and
**ADR-042**; respects **DEC-16** (dependency batch) and **DEC-44** / ADR-320.

## Context
Clients photograph IRS notices, W-2s, 1095-Cs, K-1s and bank statements. Pages without a text
layer are `not_scannable` today (P-03): no citation can point into them, no PII region can be
detected on them, and every figure must be typed by hand. Citations v2 (ADR-144) verify
`document_text` locators against a word layer; masking (P-03) burns PII regions found on that same
layer. OCR must produce that layer for scans, inside the AWS boundary, without letting client
content escape the firm's provider register and without becoming a back door around the
`ai_gateway` rules.

## Decision
1. **Provider.** **Amazon Textract**, called from `us-east-2` through an interface VPC endpoint,
   synchronous per page with the image bytes in the request (no S3 object handed over, so ADR-104's
   client-side encryption is untouched). `DetectDocumentText` for every OCR page; `AnalyzeDocument`
   FORMS only on pages code identified as a supported form; TABLES only for statement pages.
2. **Rule-6 position.** Textract is a **document service, not a model call** under AGENTS.md rule 6:
   it returns geometry and text, decides nothing and is never prompted. It therefore does not go
   through `ai_gateway`, but it carries **gateway-equivalent checks in code**, in this order: the
   `ocr.textract` kill switch, the firm's `evidence.ocr` flag, a provider-terms register entry
   covering `textract` (v2 `document_service` entries; counsel is the second approver), the
   boundary basis, and the §7216 rule through C19 for tax return information (fail closed:
   `consent_missing`, `scope_unknown`). Every call writes an `ocr_runs` usage row and refusals are
   audited without text. The adapter lives in `kernel/ocr.py`, importable only by `evidence`
   (import-linter); boto3's Textract client is imported nowhere else.
3. **Output is a derived record.** OCR words become **new** `evidence_pages` rows with
   `text_source = ocr` and an OCR extractor version in the same sealed word-layer format; earlier
   `not_scannable` rows stay as history. Citations v2 verify against that layer exactly as for a
   text layer; PII detection, masking and the masked preview then run as for any upload. The raw
   provider response is kept sealed beside the layer with the parent's retention.
4. **Extraction is code.** Form identification and box extraction use repo parameter files
   (`evidence/forms/<form>/<tax_year>.yaml`, golden-tested, reviewed yearly; DEC-76). Field
   confidence is the minimum of word and key-value confidence; below 0.90 it is `low_confidence`.
   TINs are sealed with `last4`; no model reads or sums a figure (rule 7).
5. **Fail closed, designed off states.** Flag off, kill switch, uncovered terms, missing consent,
   unknown scope or quota exceeded leave pages `not_scannable` with a refusal reason; consumers
   offer manual entry. No silent fallback to another provider or region.
6. **Dependencies.** `pillow-heif` joins the allowlist with WeasyPrint and python-docx (DEC-16);
   boto3 is already approved; `types-boto3` gains `textract` for typing.

## Options considered
### Option A: Amazon Textract inside the boundary, document service with in-code checks — chosen
- Pros: inside the existing AWS account and region; no new processor; FORMS/TABLES help on IRS
  forms; per-page synchronous calls keep encryption and retention simple.
- Cons: per-page cost; a register and counsel entry before any client page is read.

### Option B: Route OCR through `ai_gateway`
- Pros: one path for every external content call.
- Cons: the gateway's prompt, schema and budget model does not fit a geometry service; ≈ +1 task.
- Why rejected: kept as the fallback if the in-code checks are judged insufficient (P-11 R7).

### Option C: Self-hosted OCR (Tesseract)
- Pros: no provider terms.
- Cons: weak on phone photos and forms; a native dependency in the worker image; accuracy below
  the extraction thresholds.
- Why rejected: accuracy and maintenance.

## Consequences
**Positive**
- Scans get a word layer: citations, masking, search and extraction work on photographs.
- Every call is gated, recorded and refusable per firm and globally.

**Negative / costs accepted**
- Counsel must clear §7216 treatment before client tax pages are read (P-11-T18).
- Cost and quota management (page cap, budget alarm).

**Follow-up work created**
- P-11-T18 (counsel), T19/T20 (C4 v1.1 stub and consumer tests), T21 (provider-terms v2), T22
  (Terraform), T23 (OCR port), T24 (`ocr_v1`), T25 (upload step), T26–T29 (forms, corpus, evals),
  T30 (independent tests).

## Enforcement
- [x] Architecture / dependency rule in CI: import-linter contract (only `evidence` imports
      `kernel.ocr`; boto3's Textract client only in `kernel/ocr.py`).
- [x] Test: P-11-T30 fail-closed refusals, no page text or TIN in logs and audit rows.
- [x] Test: `evals/ocr_extraction/suite.yaml` thresholds (P-11-T29).
- [x] Hook or protected path: `kernel/**`, `evidence/**`, `docs/operations/provider-terms.yaml`.

## Guidance for agents
Never call Textract outside `kernel/ocr.py` and never from a module other than `evidence`. Never
treat OCR text as trusted: it is client content (ADR-052) and goes through the masked projection
before any agent sees it. Never default a counsel-gated register entry to on.
