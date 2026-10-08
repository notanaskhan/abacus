---
id: SPEC-018
title: Request list import from Excel
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-052, ADR-050, ADR-007, ADR-020]
related_specs: [SPEC-008, SPEC-016, SPEC-017]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Firms already keep their request lists ("PBC lists") in spreadsheets, and every firm's layout is different. A partner or manager can import one into an engagement in three steps:
1. upload the `.xlsx` and see its sheets, columns and a preview;
2. say which column holds the request, the audit area and, optionally, the retrievability tier;
3. confirm.

The rows become request items, matched to the engagement's methodology areas where the names agree, with duplicates skipped. Parsing and matching are deterministic code (ADR-050). Classification by model comes with increment 5.

## 2. Problem and context
Methodology templates (SPEC-008) seed a standard list, but real engagements start from last year's list or the firm's own spreadsheet. Today each item has to be typed in by hand.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement partners, managers, seniors | Import (`request_item.create`) |

## 4. Goals and non-goals
**Goals**
- **Preview:** `POST /v1/engagements/{id}/request-items/import/preview`, with the raw `.xlsx` as the body (as SPEC-008 D3). It returns:
  - each sheet's name, its column headers (from a chosen header row, default 1) and the first 20 data rows;
  - a suggested mapping (headers that read like "request", "description", "area", "section", "tier").

  Nothing is stored.
- **Import:** `POST …/request-items/import?sheet=…&header_row=…&description=…&area=…&tier=…`, with the same file as the body:
  1. parses every data row;
  2. maps areas (Q2) and normalises tiers (A to E, else empty);
  3. skips empty and duplicate rows (Q3);
  4. inserts the rest in one unit of work, auditing `request_item.created` per item and `request_list.imported` once (with the file's fingerprint and the counts).

  The response gives the counts: created, duplicates, empty, and unmatched areas.
- **Validation and limits (Q4):** 5 MB, 2,000 rows, descriptions up to 2,000 characters and areas up to 100. Problems are reported as sheet, row, column and a fixed code, never cell contents, as in SPEC-008 AC-2. The workbook is hostile input: read-only, cached values only, no formulas evaluated.
- **UI** (the Requests tab): an "Import from Excel" dialog with three steps:
  1. choose a file;
  2. choose the sheet, header row and columns, with a live preview of how rows will import;
  3. confirm.

  A summary of the counts is shown afterwards.

**Non-goals**
- Model-based classification of tiers, or of areas from descriptions (increment 5).
- Due dates, owners and client-visibility columns (a later spec, when items gain those fields).
- CSV. Excel only.
- Updating existing items from a re-import (duplicates are skipped, never changed).

## 5. User stories and acceptance criteria
- **AC-1** Given a partner, manager or senior, when they upload a workbook to preview, then they get its sheets, headers and up to 20 sample rows, plus a suggested mapping, and nothing is stored or audited.
- **AC-2** Given a mapping, when they import, then each non-empty, non-duplicate row becomes a request item:
  - its description is from the mapped column;
  - its `audit_area` is the matched methodology area's name, or the cell's text when nothing matches (Q2);
  - its tier is A to E, or empty.

  Each item is audited, `request_list.imported` is audited once, and the response gives the counts.
- **AC-3** Given rows whose (area, description) already exist on the engagement, or repeat within the file, compared case-insensitively with whitespace normalised, then they are skipped and counted, never changed (Q3).
- **AC-4** Given a workbook over the limits, malformed, or with the mapped columns missing, then nothing is imported and the problems are listed by where they are and a fixed code (Q4).
- **AC-5** Given someone without `request_item.create` (staff, reviewers, clients), then preview and import are refused (403).
- **AC-6** Given the UI, then the preview shows exactly what will be created (area matched or new, tier, duplicate) before confirming, and the counts after.

## 6. Behaviour and flows
1. **Upload:** the server parses the workbook and returns its sheets, headers, sample rows and a suggested mapping.
2. **Map and preview:** the user picks the columns. The UI previews the rows from the sample using the same matching rules, so the server and the UI agree.
3. **Confirm:** the UI re-sends the file with the mapping. The server parses all rows, validates, matches, de-duplicates, inserts, audits, and returns the counts.

## 7. Domain and data changes
None. Request items already have description, `audit_area` and `retrievability_tier` (SPEC-008). The file isn't stored, only its SHA-256 in the audit event (Q5).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `POST /v1/engagements/{id}/request-items/import/preview` | Sheets, headers, samples and a suggested mapping (AC-1) |
| `POST /v1/engagements/{id}/request-items/import?…` | Import (AC-2 to AC-4) |

Both are authorised by `request_item.create` on the engagement (not archived).

## 9. Authorisation and tenancy
No change to the matrix. Engagement-scoped, so walls and archived-write rules apply as for adding an item by hand.

## 10. AI behaviour
None (increment 5 adds model fallback for classification).

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **Merged header cells:** headers come from the chosen row only, and blank headers show as "Column C" and so on.
- **A cell that holds a formula:** its cached value is used, and an empty cache counts as empty.
- **Large files:** the limits apply before parsing completes. Rows past 2,000 are an error, not a silent truncation.
- **A methodology area renamed since:** matching is by the pinned version's area names and codes.

## 13. Security and privacy
- **Hostile input:** the workbook is parsed read-only, never evaluated, and its contents are never logged.
- **Not stored:** the file itself isn't kept.

## 14. Audit trail and evidence integrity
- **Audited:** `request_item.created` per item, and `request_list.imported` (the fingerprint and the counts).
- **Not audited:** the preview, since nothing changes.

## 15. Observability
- **Logs:** import counts and duration (no contents).

## 16. Performance and scale
2,000 rows import in one unit of work, in well under 5 seconds.

## 17. UX
- **The dialog:** a three-step stepper (file → map → confirm) in the Requests tab, in the SPEC-016 style.
- **The preview table:** columns Request · Area (matched, or "new" tagged) · Tier · Status (will import / duplicate / empty).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | unit + integration | Sheets, headers, samples, suggestions; nothing stored |
| AC-2, AC-3 | unit + integration | Mapping, area matching, tiers, duplicates, counts, audit |
| AC-4 | unit | Limits and malformed workbooks give problems without contents |
| AC-5 | integration | Matrix refusals |
| AC-6 | component | Stepper, preview and summary |

## 19. Rollout
No migration and no flag.

## 20. Open questions
- [ ] **Q1: how a firm's layout is read.** *Recommendation:* map columns on upload (sheet, header row, which columns), with a preview, because firms' layouts vary too much for one fixed template. Suggestions come from header names.
- [ ] **Q2: matching audit areas.** *Recommendation:* match the cell to the pinned methodology's area name or code, case-insensitively and with whitespace normalised. Otherwise keep the cell's text as a new free-text area, flagged "new" in the preview. Rows with an empty area go to "Unassigned".
- [ ] **Q3: duplicates.** *Recommendation:* skip rows whose normalised (area, description) already exists on the engagement or earlier in the file. Report the count. Never change existing items.
- [ ] **Q4: limits.** *Recommendation:* 5 MB, 2,000 data rows, descriptions up to 2,000 characters and areas up to 100. Over the limit is an error, not a truncation.
- [ ] **Q5: the file.** *Recommendation:* not stored. Its SHA-256 goes in the `request_list.imported` audit event, and the user re-sends it for the import step (no server-side upload store).

## 21. Future / explicitly deferred
- Model fallback for tiers and areas (increment 5).
- Due dates, owners and client-visibility columns.
- CSV.
- Re-import that updates items.
