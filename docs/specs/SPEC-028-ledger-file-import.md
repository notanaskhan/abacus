---
id: SPEC-028
title: "Ledger file import, and connect or export"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-016, ADR-037, ADR-038, ADR-040, ADR-042, ADR-045, ADR-052, ADR-107, ADR-108, ADR-110]
related_specs: [SPEC-000, SPEC-020, SPEC-022, SPEC-023, SPEC-025]
created: 2026-10-11
updated: 2026-10-11
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Clients can provide their ledger by **exporting a trial balance** from their accounting system and uploading it, instead of connecting. The export runs through the **same pipeline as a live connector** (ADR-107): stored write-once and fingerprinted, normalised, validated against control totals, snapshotted, and rendered deterministically.

The result is evidence with provenance `imported`, which fulfils tier A trial balance requests exactly as a retrieval does. The client's first screen offers **"Connect (fastest)"** and **"Export instead"** side by side, and connecting is never required (ADR-108).

This is the first way real ledgers reach Abacus. It needs no OAuth apps or partner approvals.

## 2. Problem and context
- The only connector is the fake one. A live connector needs OAuth apps, partner approvals and per-client consent, so no real ledger reaches the platform yet.
- The connector contract (ADR-037) and the pipeline (`pull_raw → normalise → validate → snapshot → render`, ADR-038) already exist. Several pieces are hardwired to the fake connector:
  - the provider list (a database CHECK);
  - the normaliser (`parse_trial_balance` reads the fake JSON);
  - `sync_runs.dataset`;
  - the evidence `method` values (`retrieved`, `uploaded`).
- Real exports differ from the fake format:
  - CSV or XLSX, not JSON;
  - signed balances, where a negative amount means a credit;
  - usually no declared control totals, sometimes a "Total" row;
  - no currency column;
  - header rows and notes above the table.
- A client can already upload any file to an item (method `uploaded`), but that file isn't normalised, validated or snapshotted, so it can't serve tier A requests, and later ledger cross-checks can't use it.

## 3. Actors
| Actor | Role here |
|---|---|
| Client admin (the story's Rachel) | Chooses connect or export; exports from their system following the guide; uploads; sees the result |
| Engagement partner, manager, senior | See what was imported and its checks; may import on the client's behalf (Q4) |
| The platform (code) | Scans, normalises, validates, snapshots, renders; fulfils tier A trial balance items; explains failures in plain words |

## 4. Goals and non-goals
**Goals**
1. **An import connector** (`provider = "import"`, ADR-107):
   - capabilities: datasets `trial_balance`; `oauth`, `incremental` and `attachments` all false;
   - `pull` reads the uploaded export for the requested period;
   - `changes_since` and `fetch_attachment` raise `NotSupported`; `health` reports the latest import;
   - it's added to the provider list (database CHECK), the connector registry and the conformance suite.
2. **Uploading an export:**
   - a **ledger import** record holds the stored file (write-once, fingerprinted, ADR-016), the chosen format, the period, who uploaded it, and its status;
   - the client picks their system and format, then the period (prefilled from the engagement's fiscal year);
   - the file is malware-scanned before any parsing (ADR-110; the scanner interface with a local stub, shared with SPEC-029);
   - an import becomes the engagement entity's active "connection" of provider `import`, so tier A trial balance items are retrievable, and automatic retrieval (SPEC-022) starts the pipeline as it does for a live connector.
3. **Format mappings as configuration** (ADR-107):
   - each format (for example `qbo_trial_balance_csv`, `xero_trial_balance_xlsx`) declares where the table starts, the account code and name columns, and the amount columns;
   - amounts are either separate debit and credit columns, or one signed balance column whose sign decides debit or credit;
   - the total row's label and the date or period cell, where present;
   - the mapping is applied as plain code at run time. The first two formats are **QuickBooks Online** and **Xero**; NetSuite, Sage Intacct and QuickBooks Desktop follow in a later task (Q1).
4. **Normalising imports:**
   - CSV and XLSX; XLSX read for cached values only, formulas never evaluated, macros ignored (ADR-110);
   - the existing limits apply: 20 MB, 50,000 lines, strict text, no control characters;
   - amounts accept signs, thousands separators and parentheses for negatives;
   - **control totals:** the file's own total row where the format has one; otherwise the sums of the lines (Q2);
   - **currency:** USD unless the file says otherwise (Q3); anything else is refused, as today;
   - the existing ledger validation applies unchanged (balanced, no duplicates, totals match, period matches, not empty).
5. **Provenance `imported`:**
   - a new evidence method;
   - the rendered workbook's provenance footer says "Imported from a {system} export uploaded by {name} on {date}" (ADR-042, deterministic);
   - the Board and item detail show "Imported" beside "Retrieved" and "Uploaded".
6. **Guided export steps** per system, as configuration: plain numbered steps ("In QuickBooks Online: Reports → Trial Balance → set the period → Export → Export to CSV") shown before the upload, with the expected file type.
7. **Connect or export (ADR-108):**
   - the client's engagement page opens with two options side by side: **Connect (fastest)**, with today's consent dialog, and **Export instead**, with the system picker, guided steps and upload;
   - connecting is never required. After an import, the panel shows the latest import's period, status and date, with "Upload a newer export".
8. **Plain words for failures:**
   - unbalanced: "Debits and credits differ by $1,250.00";
   - wrong period: "This export covers 1 Jan–30 Nov 2026; we need the year ending 31 Dec 2026";
   - unreadable;
   - not the format chosen: "This looks like a Xero export; you chose QuickBooks Online";
   - unsupported currency.

   Each comes from a fixed template, shown to the client at once (ADR-111).
9. **Request wording adapts to capabilities:** a trial balance item met by an import says "Provided by your export of {date}". Because imports aren't incremental, a later period asks for a new export instead of promising a refresh.

**Non-goals**
- General ledger detail (transactions). The ledger only stores trial balances today; GL detail needs its own snapshot table and validation (the GL reconciling to the TB). It's the next spec (Q5).
- Other datasets (AR/AP aging, journals).
- NetSuite, Sage Intacct and QuickBooks Desktop formats (a follow-up task, Q1).
- Live connectors (QuickBooks API and others): after this, per ADR-107.
- Model-based format detection: detection is by header signature (code).
- OCR or PDF trial balances: CSV and XLSX only.

## 5. User stories and acceptance criteria
- **AC-1** Given a client admin on the engagement page, then they see "Connect (fastest)" and "Export instead" side by side. Choosing export needs no connection, and connecting stays available.
- **AC-2** Given "Export instead", when they pick QuickBooks Online or Xero, then they see that system's numbered export steps and the expected file type, and can upload a file for a period (prefilled from the fiscal year).
- **AC-3** Given an uploaded export, then it's stored write-once with its fingerprint, malware-scanned before anything parses it, and recorded as a ledger import. A file that isn't scanned clean is never parsed.
- **AC-4** Given a clean export in a known format, then the pipeline normalises it, validates it, snapshots it and renders the trial balance workbook. The evidence has method `imported`, and its footer names the system, uploader and date. Tier A trial balance items for that period are fulfilled, as by a retrieval.
- **AC-5** Given signed balances, parenthesised negatives, thousands separators or a total row, then they're read correctly. Debits equal the positive balances, credits the negatives, and the control totals come from the total row or the lines (Q2).
- **AC-6** Given an export that fails validation, then the client sees a plain, fixed message saying what's wrong, nothing is snapshotted or fulfilled, and the firm sees the same reason on the item.
- **AC-7** Given an import, then the import connector reports its capabilities (no OAuth, no change feed, no attachments). `changes_since` and `fetch_attachment` raise `NotSupported`, and it passes the connector conformance suite.
- **AC-8** Given the same export uploaded twice, then the second is recognised by fingerprint and creates no second snapshot (as for retrievals).
- **AC-9** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. Rachel opens the engagement and chooses **Export instead**.
2. She picks QuickBooks Online and sees the steps. She exports the year-end trial balance as CSV and uploads it.
3. The file is stored write-once and scanned.
4. The import becomes the entity's active import connection, and automatic retrieval starts the pipeline for the open tier A trial balance items. The import connector's `pull` reads the stored export, the format mapping normalises it, the ledger validates it, then the snapshot and render follow, and the evidence (`imported`) fulfils the item.
5. Rachel sees "Provided by your export of 12 Jan 2027". If it failed, she sees the reason and "Upload a corrected export".

## 7. Domain and data changes
- **connections:**
  - the `import` provider (CHECKs on `connections.provider` and `connection_states.provider`);
  - `ledger_imports` (engagement, entity, format, period, storage key, version, fingerprint, size, scan status, status, uploaded by, at);
  - format mappings as code configuration (`connections/import_formats.py`).
- **evidence:** method `imported` (CHECK and Literals); `pulled_at` holds the upload time.
- **The malware scanner interface** (`kernel` or `evidence`, decided in the task), with a local stub that refuses the standard test signature.

## 8. Interfaces
- `GET /v1/engagements/{id}/ledger-import/formats`: systems, formats and their steps.
- `POST /v1/engagements/{id}/ledger-import?format=…&period_start=…&period_end=…` (raw body, like uploads): returns the import.
- `GET /v1/engagements/{id}/ledger-import`: the latest import and its status.

## 9. Authorisation and tenancy
- The new matrix action `ledger_import.upload` is held by the client admin, and by the partner, manager and senior if Q4 says so.
- Reading an import's status uses `connection.read_log`'s roles.
- Everything is tenant-scoped, and the gate applies: no import before the engagement is open (SPEC-025).

## 10. AI behaviour
None. Format detection and normalisation are code (ADR-050).

## 11. Integrations
None live. The guided steps describe each system's own export screens.

## 12. Edge cases and failure modes
- A CSV with a byte-order mark, or in Windows-1252: accepted only as UTF-8 or a declared encoding (Q6).
- A trial balance with sub-total rows: the mapping skips rows with no account code.
- An export covering a different period: refused as `period_mismatch`, with both periods in the message.
- A newer import for the same period: a new snapshot, superseding by period (as retrievals do); earlier evidence versions stay.

## 13. Security and privacy
- The file is hostile (ADR-052). It's scanned before parsing, parsed with limits, formulas are never evaluated, and the raw file is never rendered in a browser.
- Account names are untrusted text; they're stored and rendered as data.

## 14. Audit trail and evidence integrity
- The raw export is kept write-once with its fingerprint, and the snapshot is linked to it.
- Each import, scan result and pipeline outcome is audited.

## 15. Observability
Counters per format and outcome (scanned, refused, validated, failed, by reason).

## 16. Performance and scale
Up to 50,000 lines in one import (the pipeline's existing limit).

## 17. UX
- The two options sit side by side as equal cards. "Fastest" is a label on Connect, not a nudge that hides Export.
- Each system's steps are numbered, with the menu path and file type, plus "Need help? Your auditor can upload it for you" (Q4).

## 18. Test plan
| AC | Type | Notes |
|---|---|---|
| AC-5, AC-6, AC-8 | unit | Each format's fixtures: signed, parentheses, totals, sub-totals, wrong period, unbalanced |
| AC-7 | unit | The connector conformance suite for `import` |
| AC-3, AC-4 | integration | Scan, then the pipeline, then evidence `imported`, then fulfilment |
| AC-1, AC-2, AC-9 | vitest | The two options, guided steps, upload, states |

## 19. Rollout
Behind the per-firm flag `ledger.import`, on for Dev firm locally. Synthetic export fixtures for both formats live in `abacus_tools.synthetic`.

## 20. Open questions
All resolved: the founder approved every recommendation below on 2026-10-11.
- **Q1. Start with QuickBooks Online and Xero only, then NetSuite, Sage Intacct and QuickBooks Desktop in a follow-up task?** *Recommendation: yes* (agreed in principle; confirm). Each format needs real sample exports, so please share anonymised samples if you have them.
- **Q2. Control totals with no total row in the file: use the sum of the lines (so the check is "balanced" only), or ask the client to type the totals from their system?** *Recommendation: use the file's total row when present; otherwise sum the lines and label the evidence "control totals from the lines".* Typing totals adds friction for little assurance.
- **Q3. Currency: assume USD when the export has none (US firms), refusing anything marked otherwise?** *Recommendation: yes.*
- **Q4. May the partner, manager or senior upload an export on the client's behalf (as SPEC-023 allows for documents)?** *Recommendation: yes*, recorded as uploaded on behalf, with the client shown.
- **Q5. General ledger detail as the next spec (its own snapshot table and the GL-to-TB reconciliation)?** *Recommendation: yes.*
- **Q6. Encodings: UTF-8 (with or without BOM) only, or also Windows-1252, common in Excel CSV exports?** *Recommendation: UTF-8 and Windows-1252, detected by code, nothing else.*

## 21. Future / explicitly deferred
- GL detail, AR/AP aging and journals imports.
- More formats.
- Live connectors (QuickBooks API first, per ADR-045).
- The ledger cross-checks in SPEC-029 build on these snapshots.
