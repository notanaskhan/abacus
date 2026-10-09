---
id: TASK-039
title: Uploads on the client's behalf, the inbox and matching
spec: SPEC-023
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: done
branch: task-039-uploads-matching
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-023 (approved, Q1–Q5): uploads on the client's behalf, the engagement inbox, rule-based match suggestions and confirming them.

## Scope
All of SPEC-023.

## Context to load
- Spec: `docs/specs/SPEC-023-uploads-on-behalf-and-matching.md`
- Code: `evidence/uploads.py` (checks, storage, `add_version`, `fulfil_by_upload`), `evidence/item_detail.py`, `requests.api` (`read_item`, `request_items_for`, `classify`), `apps/web` `ClientEngagement`, `ItemDetail`, `Board`

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D3). Approved by founder: paths listed under *Protected paths*

### Design (for founder review)
1. **On behalf (`uploads.py`):**
   - `upload(..., on_behalf: bool, note: str | None)`;
   - on behalf requires the caller to hold a staff role on the engagement (a client role is refused), plus `evidence.upload`;
   - source `firm_upload_for_client`;
   - the note (up to 500 characters, plain text) goes in a new nullable `evidence_versions.upload_note` column (D1);
   - `UploadView` gains `on_behalf` and `note`. The client's history shows "Added by your auditor", and the firm's item page shows the note.
2. **Inbox (migration 0031, `evidence/inbox.py`):**
   - **The table** `inbox_files`: id, tenant, engagement, file name (cleaned), media type, size, fingerprint, the stored object, uploaded by, note, status (`waiting`, `assigned`, `discarded`), assigned item and version, decided by and at, created at;
   - forced RLS; the app may insert, and update only the status and decision columns;
   - one waiting file per fingerprint per engagement (a partial unique index), which refuses duplicates.
   - **Add:** `add_to_inbox` uses the same checks as SPEC-020 (authorise `evidence.upload` on the engagement before the body is read; size, type by content, duplicate), stores the bytes and inserts the row, audited `inbox_file.added`.
   - **List:** staff see every waiting file; client admins see the clients' files; contributors see only their own.
   - **Assign** (`evidence.upload` with the target item's facts, as SPEC-020):
     1. lock the inbox row and the item;
     2. `add_version` from the stored object, with the evidence item titled with the file name, and source `client_upload` (or `firm_upload_for_client` when staff added it);
     3. `fulfil_by_upload`;
     4. set the row to `assigned`;
     5. audit `inbox_file.assigned` with `followed_suggestion` (0/1, sent by the client from the suggestion it picked), and emit `EvidenceUploaded`.
   - **Discard:** the uploader, or a staff member allowed `evidence.upload`; status `discarded`, audited.
3. **Matching (`evidence/matching.py`, pure):**
   - computed when the inbox is read, against the items the reader can see, so suggestions reflect current statuses and contributors only see their assigned items (D2);
   - **file-name tokens:** lowercase words (camel case and separators split, extension and digits-only parts dropped, a short stopword list);
   - **score:** the share of the item's significant words found in the file name, plus a hint bonus when the file name matches the same classification rule as the item (for example "TB" and the trial balance item), capped at 100;
   - **output:** at most three items that take evidence, scoring at least 35, each with its score and matched words.
4. **Routes (evidence router):**
   - `POST /v1/engagements/{id}/inbox?filename=…&note=…`
   - `GET …/inbox`
   - `POST …/inbox/{file_id}/assign` with body `{request_item_id, followed_suggestion}`
   - `POST …/inbox/{file_id}/discard`
   - the existing upload route gains `on_behalf` and `note`.
5. **Web:**
   - **Inbox panel:** a drop zone that uploads each file with its status, and a list with suggestion buttons, an item picker, Assign and Discard. It sits on the client engagement page and above the Board (staff).
   - **"Upload for the client":** on the item page, with a note.
   - **History:** the client portal's upload history says "Added by your auditor".

**Protected paths (approval file):** `backend/src/abacus/modules/evidence/**`, `backend/tests/unit/**`, `backend/src/abacus_tools/quality/schema_check.py` (the new table and column) and `backend/src/abacus_tools/quality/banned_patterns.py` (in case the inbox list needs LIST-001 handling). I checked these, and they don't change:
- the matrix: no new actions;
- `api/app.py`: no new router;
- identity: uses `engagement_role_of` and `names_of` only;
- requests: exports `classify`; not protected.

### Questions for approval
- **D1. Store the on-behalf note in a new nullable `evidence_versions.upload_note` column (written once at insert, so the table stays immutable)?** *Recommendation: yes.*
- **D2. Compute suggestions when the inbox is read, rather than storing them at upload?** *Recommendation: yes.* They stay right as items change, and contributor scoping comes free.
- **D3. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Implemented:
  - migration 0031 (`upload_note`, `inbox_files`);
  - on-behalf uploads (staff only, with a note, shown as "Added by your auditor" to the client and with the note on the item page);
  - the inbox (add, list by role, assign through the shared `uploads.attach`, discard);
  - the rule matcher (file-name words, rule bonus, version markers dropped);
  - the Inbox panel on the client page and the Board, and "Upload for the client" on the item page.

  Tests and checks:
  - backend unit and web 162 passed; the gates pass;
  - migration 0031 applies, rolls back and reapplies;
  - a local smoke passed: a suggestion scored 100 with its matched words; the duplicate refused; assign and discard worked; the on-behalf version kept its note.

  The smoke's request item and its two evidence versions stay in the local database (evidence can't be deleted).
- `2026-10-09` — SPEC-023 approved and merged (#72). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
