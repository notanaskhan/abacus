---
id: TASK-035
title: Client portal, item visibility and client uploads
spec: SPEC-020
acceptance_criteria: [AC-1, AC-7, AC-8, AC-9]
risk_zone: red
status: awaiting-plan-approval
branch: task-035-client-portal-uploads
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
Implement the client half of SPEC-020: clients can see their engagement's request items and upload files to them. The connection flow (AC-2 to AC-6) is TASK-036 (D1).

## Scope
SPEC-020 §4 "Client engagement page" and "Manual upload"; AC-1, AC-7 (for these screens), AC-8, AC-9.

## Context to load
- Spec: `docs/specs/SPEC-020-client-portal-and-connection.md`
- Code: `identity.authz` (`authorise`, `visible`, `Resource`, the matrix conditions), `requests` (models, repository, `fulfil_by_rule`, routes), `evidence` (`add_version`, `Provenance`, `storage.put`), `notifications` catalogue, `apps/web` client portal (`ClientHome`) and `Board`

## Plan
- [ ] Plan approved by human

### What the code shows
- **Clients see nothing yet.** The matrix conditions `client_visible_only` and `assigned_only` are not modelled; `authorise` treats them as denials. Clients can't read items or upload.
- **Items have no client fields:** no visibility flag, no client assignee, and no due date (SPEC-020 §4 mentions due dates "where set"; there are none, so none are shown).
- **Uploads already have a provenance method** (`uploaded`), but no route stores one. `fulfilment.propose` (which `fulfil_by_rule` checks) has no client rows.

### Design (for founder review)
1. **The conditions in `authorise` (D2, identity):**
   - `Resource` gains optional item facts: `client_visible` and `client_assignee`;
   - `client_visible_only` allows when the item is client-visible; `assigned_only` when it's client-visible and assigned to the actor; without item facts both still deny;
   - `visible()` gets an item-level twin for list queries (`visible_items(ctx, action, item columns)`), agreeing with `authorise` for every role;
   - only `request_item.read`, `evidence.read` and `evidence.upload` use the conditions today; the rest stay denials.
2. **Item fields (requests migration, D3, D4):**
   - `request_items.client_visible boolean NOT NULL DEFAULT true` and `client_assignee_user_id uuid NULL` (must be a client member of the engagement, checked in the service);
   - `PUT /v1/engagements/{id}/request-items/{item_id}/client-visibility` (`request_item.update`): a "Hidden from client" switch on the Board;
   - `PUT …/client-assignee` (`request_item.assign`): a client admin assigns an item to a contributor (or clears it) in the portal; firm staff can too.
3. **Uploads (evidence and requests, D5, D6):**
   - `POST /v1/engagements/{id}/request-items/{item_id}/uploads`, raw body, query `filename`, header `Content-Type` (advisory only);
   - order: lock the item, authorise `evidence.upload` with the item's facts; check status (open, received, needs revision); check size (25 MB); sniff the type from the leading bytes; refuse a duplicate (same SHA-256 already on this item); `storage.put`; `add_version(method="uploaded", source="client_upload")`; `requests.fulfil_by_upload` links it and marks the item received (kind `human`, authorised by the caller's `evidence.upload`, no matrix change); audit `evidence.uploaded`; notify the item's firm team (`evidence.uploaded` kind);
   - `GET …/uploads` (`evidence.read`): the item's uploads (file name, uploader's name, size, when).
   - File names are untrusted text: stored length-capped with control characters removed, shown as plain text only.
4. **Portal (web):**
   - `ClientHome` lists the client's engagements; `/client/engagements/$id` (`ClientEngagement.tsx`) shows items by area with status, an "Upload files" control per item (several files, one request each, with progress) and its upload history;
   - client admins get an assignee picker per item (contributors from the engagement's client contacts);
   - the Board gets the "Hidden from client" switch.

**Protected paths (approval file):** `backend/src/abacus/modules/identity/**`, `backend/src/abacus/modules/evidence/**`, `backend/tests/unit/**`. Requests, notifications and `apps/web` aren't protected; the matrix file is unchanged.

### Questions for approval
- **D1. Split SPEC-020 into TASK-035 (this: visibility, assignment, portal, uploads) and TASK-036 (connection flow, health, access log, revoke)?** *Recommendation: yes.* Each is red-zone and large; uploads don't depend on connections.
- **D2. Model `client_visible_only` and `assigned_only` in `authorise` with item facts on `Resource`, plus an item-level list filter?** *Recommendation: yes.* It's the only way clients can see anything, and it keeps one decision point (ADR-020).
- **D3. New items are client-visible by default, with a "Hidden from client" switch on the Board?** *Recommendation: yes.* A request list exists to be sent to the client.
- **D4. Client admins assign items to contributors in the portal?** *Recommendation: yes.* Without it contributors see nothing (`assigned_only`).
- **D5. Uploads link to the item through a new `requests.fulfil_by_upload`, authorised by the caller's `evidence.upload`, rather than adding client rows to `fulfilment.propose`?** *Recommendation: yes.* No matrix change.
- **D6. File types are detected in-house from leading bytes (PDF, PNG, JPEG, OOXML zip with its content-types part, legacy OLE for .xls and .doc, CSV as UTF-8 text without NUL bytes), with no new dependency?** *Recommendation: yes.*
- **D7. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — SPEC-020 approved and merged (#65). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
