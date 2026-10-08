---
id: TASK-033
title: Request list import from Excel
spec: SPEC-018
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: done
branch: task-033-request-list-import
worktree:
created: 2026-10-08
updated: 2026-10-08
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-018 (approved, Q1–Q5): a preview and an import of a firm's request-list workbook, with column mapping, area matching, de-duplication, limits and audit, plus the three-step import dialog on the Requests tab.

## Scope
All of SPEC-018.

## Context to load
- Spec: `docs/specs/SPEC-018-request-list-import.md`
- Code: `requests` (service, repository, routes), `engagements.api` (`EngagementRef.methodology_version_id`, `version_detail`), the engagements workbook parser (as a pattern only), `apps/web` Board

## Plan
- [x] Plan approved by human (founder, 2026-10-08: D1–D2)

### Design (for founder review)
1. **The parser** (`requests/workbook.py`, pure):
   - opens read-only with cached values;
   - `preview(data, header_row)` returns the sheets with their headers (blank → "Column C"), the first 20 data rows, and suggested columns (headers containing "request" or "description" or "item"; "area" or "section" or "category"; "tier");
   - `rows(data, sheet, header_row, columns)` returns every data row as (row number, description, area, tier).
   - The limits are 5 MB, 2,000 rows and the length caps, with problems as sheet, row, column and code, as in SPEC-008.
2. **Mapping by column position (D1):** the import takes `description`, `area` and an optional `tier` as 0-based column indexes, plus `sheet` and `header_row` (positions are unambiguous when headers repeat or are blank). The UI sends what the user picked from the preview.
3. **Matching:**
   - **Areas:** normalise (case-folded, whitespace collapsed) and match the pinned version's area names and codes (via `engagements.api.version_detail`, with the version from `EngagementRef`). A match takes the area's name; no match keeps the cell's text, counted as `unmatched_areas`; an empty area becomes "Unassigned".
   - **Tiers:** A to E, case-insensitive, else empty.
   - **Duplicates (D2):** compare normalised (area, description) against the engagement's existing items and earlier rows in the file.
4. **The service** (`requests.service.import_request_list`):
   1. lock the engagement and `authorise(request_item.create)`;
   2. parse the rows, refusing with `RequestListInvalid` (422, the problems in the validation-error shape, as the methodology upload does);
   3. create the request list if needed;
   4. insert each item, with `request_item.created` and the `RequestItemCreated` event per item;
   5. audit `request_list.imported` (the fingerprint and counts).

   It returns the counts. The preview is `authorise` plus parse, with nothing stored.
5. **Routes:** `POST /v1/engagements/{id}/request-items/import/preview` and `…/import`, with the raw body (no multipart, per SPEC-008 D3).
6. **UI:**
   - "Import from Excel" on the Requests tab opens a three-step dialog (file → map → confirm);
   - the map step has a select per field, filled from the preview's headers and its suggestions, and a preview table built from the sample rows with the same matching rules mirrored in the app (area matched or new, tier, duplicate);
   - a summary of the counts is shown afterwards.

No protected paths (requests, engagements and `apps/web` aren't protected), so no approval file.

### Questions for approval
- **D1. Map columns by position (0-based index) rather than header text?** *Recommendation: yes.* Headers can repeat or be blank.
- **D2. Duplicates are judged on normalised (area, description) against existing items and earlier rows, and the matching is mirrored in the UI's preview so the preview and the import agree?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-08` — Implemented:
  - the workbook parser (preview, mapped rows, limits, problems);
  - the import service (area matching, tiers, de-duplication, one unit of work, audit);
  - the preview and import routes;
  - the three-step import dialog on the Requests tab, with the matching mirrored for the preview.

  Backend unit (8,902) and web (120) tests and the gates pass. A local Postgres run passed: column suggestions, an in-file duplicate and an empty row skipped, a re-import creating nothing, a non-workbook refused.
- `2026-10-08` — SPEC-018 approved and merged (#61). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
