# requests

Request lists and request items (glossary). Owns `request_lists` and `request_items` (ADR-103).

## Public interface (`api.py`)
- `router`: `POST /v1/engagements/{id}/request-items` (`request_item.create`) and `GET /v1/engagements/{id}/request-items` (`request_item.read`).
  - Each listed item carries `evidence_version_id`: the version of its most recent fulfilment, or null.
  - The evidence board joins evidence and screening on it (TASK-012 Q1).

## Rules
- Review (SPEC-004): `fulfilled_versions(ctx, engagement_id)` (`review.read`, `visible()`) and `move_after_review(tx, item_id, to)`. The second moves only `received`, `ready_for_review` or `needs_revision` to `accepted`, `received`, `open` or `needs_revision`, audited `request_item.<to>`. A sent-back (`needs_revision`) item takes new evidence and becomes `received`.
- An engagement has one request list, created with its first item.
- New items are `open`. Audit event: `request_item.created`. Outbox event: `request_item.created`.
- Both routes resolve the engagement with `engagements.api.get_ref` (404 outside the tenant) and authorise before reading or writing. The list also applies `visible(ctx, "request_item.read", RequestItem.engagement_id)`.

## Applying a methodology (SPEC-008)
`POST /v1/engagements/{id}/methodology` (`engagement.apply_methodology`) applies a template version to the engagement:
- it pins the version (409 `methodology_already_applied` if one is already pinned);
- it creates one request item per template item, with the area name as `audit_area` and the item's `retrievability_tier`.

Items added by hand are never changed.

## Request list import (SPEC-018; TASK-033)
`POST …/request-items/import/preview` and `…/import` take the raw `.xlsx` as the body.

**Preview:** the sheets, headers, sample rows and suggested columns.

**Import:** columns are mapped by position (`description`, `area`, optional `tier`).
- **Areas** match the pinned methodology's names or codes, ignoring case and spacing; otherwise the cell's text is kept, and a blank area becomes "Unassigned".
- **Duplicates** (by area and request, normalised) are skipped and never changed.
- **Audit:** each item is audited, and `request_list.imported` records the file's fingerprint and the counts.

The parser (`workbook.py`) is read-only, bounded (5 MB, 2,000 rows), and reports problems without cell contents.

## Client facts (SPEC-020; TASK-035)
- **Columns:** `client_visible` (default true) and `client_assignee_user_id` (a member of the item's engagement; the service requires a client contributor).
- **Routes:**
  - `PUT …/request-items/{item_id}/client-visibility` (`request_item.update`);
  - `PUT …/client-assignee` (`request_item.assign`, 409 `not_a_client_contributor`).
- **Uploads:** `fulfil_by_upload` links an uploaded version to its item and marks it received, for a caller that authorised `evidence.upload` on the item.

## Classification (SPEC-022; TASK-038)
- **`classification.py`:** ordered keyword rules (stable IDs, audited).
  - Precedence: override > the firm's own tier (methodology or imported list) > rule > unclassified.
  - A items name their `dataset`.
- **When items are classified:** on insert (add, import, methodology), audited `request_item.classified`. `RequestItemClassified` is emitted for A items with a dataset.
- **Overrides:** `PUT …/request-items/{item_id}/tier` (`request_item.update`), audited `request_item.tier_overridden`. Clearing the override reapplies the rules.
- **Availability:** `available` on each item comes from the live connection's capabilities, through `register_available_datasets` (connections registers it, ADR-106). Unregistered means nothing is available.
- **SPEC-027 (TASK-051):** due dates: `request_items.due_on` and the list's `default_due_on` (`PUT …/request-items/due-dates`, `GET/PUT …/request-items/default-due-date`, `request_item.update`); `due_dates.changed` tells the engagement agent; `overdue_for` lists open or sent-back items past due for its reminders.

## Document kinds (SPEC-029; TASK-055)
- `document_kind` (`bank_statement`, `ar_aging`, `ap_aging`, `schedule`) by fixed keywords (`classification.KIND_RULES`) on create, carried on roll-forward; the team sets or clears it (`PUT …/request-items/{id}/document-kind`, `request_item.update`), which emits `request_item.document_kind_changed`.

## Guidance and your part (SPEC-031; TASK-060)
- `request_items` carry `why`, `good_looks_like`, `still_needed` (up to 1,000 characters), `blocks_fieldwork`, `effort` (`small`, `medium`, `large`) and `guidance_source` (`template`, `kind_default`, `firm`).
- **Defaults (`guidance.py`):** on insert, the template's text, else the fixed copy for the document kind (`KIND_DEFAULTS`, founder-approved), else empty. A kind change replaces only kind-default copy. Roll-forward copies guidance, not the still-needed note.
- **Firm editing:** `PUT …/request-items/{id}/guidance` (`request_item.update`), audited `request_item.guidance_set`; the source becomes `firm`.
- **Your part:** `GET …/request-items/your-part` (client roles; others get zeros): open or sent-back client-visible items assigned to the person, or unassigned for client admins; minutes 15/45/120, unestimated counted as medium.

## Comments (SPEC-032; TASK-062; ADR-109)
- **Threads (`comments.py`):** one per request item and one per evidence version that fulfils it. `comments`, `comment_mentions` and `comment_redactions` are insert-only; `comment_reads` keeps each person's last read per thread.
- **Visibility:** a firm member's comment is internal unless shared (`comment.share`); a client's is always shared. Client roles only ever receive shared comments, on items they may read (`visible_items` with `comment.read`).
- **Sharing:** a firm comment is checked by the scope check communications registers (`register_comment_scope_check`); a violation or checker error refuses it (409 `out_of_scope`), and nothing registered refuses sharing (409 `sharing_unavailable`).
- **Corrections:** same author, same thread, not redacted; the correction keeps the original's visibility.
- **Mentions:** only people who may read the comment (the firm team; for shared comments also the item's client admins and assigned contributor); `comment.mentioned` notifies each.
- **Redaction:** `comment.redact` (firm admin, recent MFA), once, with a reason; the sealed text stays and is never returned again.
- **Text:** Restricted, sealed with `kernel.crypto` (bound to its SHA-256), never logged; audit events carry identifiers and the fingerprint only.
- **Routes:** `GET/POST …/request-items/{id}/comments`, `GET/POST …/{id}/versions/{version}/comments`, `GET …/{id}/comments/mention-candidates`, `POST …/{id}/comments/read`, `POST …/{id}/comments/{comment}/redact`. The request list carries `comment_count` and `unread_comments`.
- **Drafted guidance (SPEC-035; TASK-073):** `apply_drafted_guidance` (inside the caller's unit of work, `request_item.update`) writes approved drafter text with source `drafted` and `guidance_approved_by`. For client roles, `request_items_for` replaces drafted guidance with the kind default, or nothing, unless the firm's `drafted_guidance_to_clients` is on (identity; synthetic firms only, ADR-111/112). A kind change keeps drafted guidance; a firm edit makes it `firm`.

## Binder lifecycle (P-06-T07; C5 v1; SPEC-319 AC-5 to AC-9)
`binders.py`, behind `binders.engine` (404 when off). The routes are in `contract.py`.
- **Create** (`binder.create`): a Draft on a work item, numbered by part per kind. It starts blank, from a firm template (`template_ref` kept; K-01 fills templates), or from last year's binder. The prior-year route copies the binder's sections and requests through `roll_forward.copy_binder_items`: tagged `prior_year`, the still-needed note dropped, no assignee, no due date.
- **Duplicate** (`binder.create`): the next part, empty, with the same sections and recipients.
- **Read** (`binder.read`): the record with categories, counts, recipients and `allowed_actions`. `GET …/requests` lists rows through `visible_items`. The client preview shows client-visible rows only. Activity (`activity.read`) reads the binder's and its requests' audit events through `kernel.uow.audit_of_targets`. To a client, a binder that isn't published, or isn't in their scope, is 404 (INV-4).
- **Publish** (`binder.publish`, a person only, `Idempotency-Key`):
  - G3 first, except an `intake` binder (409 `binder_gate_unmet`).
  - Every request sent needs a due date (422 `due_date_required`).
  - Client-visible, never-sent requests get `sent_at`/`sent_by`.
  - `binder.published` is held by an approval grant until business now + 10 s.
- **Undo:** within 10 s it voids the grant, so the relay delivers nothing, and puts the binder and requests back. After 10 s: 409 `undo_window_closed`. After the grant is consumed: 409 `effect_started`.
- **Unpublish** needs a reason. The reason is sealed; the audit keeps its fingerprint.
- **Recipients:** the engagement's client's contacts (`engagements.api.client_contact_names`). The history is insert-only.
- **Mark-done** (`binder.mark_done`, the client): Published to Complete, recording the open count.
- **Close:** `SUBSCRIPTIONS` closes non-terminal binders on `work_item.status_changed` or `engagement.status_changed` into `delivered`/`archived`. Kinds add theirs with `register_binder_close_rule`.

### Binders index (P-06-T11; `binder_index.py`)
- `GET /v1/binders` (`binder.read`): BND-01's rows, tiles (`counts` per status, without the tile), total and facets, from one statement under `visible()` (`repository.binder_index`), so walled binders are absent everywhere (INV-3, DEC-43).
- Work-item facts (kind, season, office, preparer, client and work item names) come from `engagements.api.work_item_index()`, joined on the binder's work item.
- `binder_activity` is the projection it reads for the last client activity; the client's mark-done keeps it (`repository.touch_client_activity`).
- **Slot:** `register_binder_tag(code, provider)`: a provider names, of a page's binders, those carrying its tag (the §7216 consents tag: P-07, T-01). None registered, no tags.

## Request lifecycle v2 (P-06-T10; C5 v1; SPEC-319 AC-11 to AC-14)
`lifecycle.py` (PROTECTED), routes in `contract.py`, behind `binders.engine`. Every move is a person's (INV-1) except the client's Ignore.
- **Edit and delete:** `PATCH …/request-items/{id}` edits a non-terminal request (`request_item.update`); `DELETE` soft-deletes a never-sent Draft only (409 `request_already_sent`).
- **Send** (`request_item.send`, `Idempotency-Key`): Draft to Requested.
  - It needs a due date, its own or the binder's (422 `due_date_required`).
  - Unchanged model-drafted wording is refused while the firm's P-25 setting is off (409 `model_text_not_permitted`, DV-11), compared by `drafted_wording_fingerprint`.
  - The title and wording pass `communications`' scope check (409 `out_of_scope`, nothing sent; with no check registered, 409 `sharing_unavailable`).
  - The `request_item.sent` email is held by an approval grant until the 10-s Undo window ends (ADR-161), as a binder's publish is. Undo after 10 s: 409 `undo_window_closed`; once delivered: 409 `effect_started`.
- **Waive** (`request_item.waive`, a reason): to `not_applicable`. **Ignore** (the client, `POST /v1/portal/request-items/{id}/ignore`, a reason): the status stays `requested` with `client_ignored_at` (OQ-3). **Return to client** (`request_item.return`) clears it. **Incorporate** (`request_item.update`): `pending_incorporation` to `incorporated`.
- **The client's Undo** of an Ignore or a Mark as Done (`client_undo.py`, R-01-T08): a compensating event, by the person who acted, open until the firm acts (409 `firm_already_acted`).
- **Delegate** (`request_item.delegate`): a client contact who is a portal user (else 409 `contact_not_portal_user`) gets a `request_item` grant on this one request (P-09), recorded in `request_delegations`. On an engagement holding a `tax_return` work item it needs the client's §7216 `third_party_disclosure` consent (`consent.py`; 409 `consent_required`; nobody holds it until T-01 registers C19, DEC-388).
- **Activity** (`activity.read`): the request's audit events through `kernel.uow.audit_of_targets`, identifiers only.
- **Upload intents** (`POST /v1/portal/request-items/{id}/upload-intents`, `evidence.upload`): a 90-second hint in the UNLOGGED `request_upload_intents`, audited `upload_intent.announced`. Expired rows are ignored at read; nothing sweeps them.
- **The live poll** (`GET /v1/binders/{id}/live`, `request_item.read`; BND-02 every 5 s): unexpired intents per request, plus inbox files waiting and a screening running from the provider registered with `register_live_facts`. **No module registers that provider yet**, so on the live stack both read 0 and false (DEC-158); fixture mode draws "Waiting 2".

## What follow-ups chase (P-06-T14; `follow_up_reads.py`)
The agents module drafts follow-ups and reads the requests only through this. A request is chased while it is open for the client: Requested or Returned, client-visible, not deleted, in a Published binder (otherwise 409 `binder_not_published`). A screening return names a request the client answered: Uploaded, or Returned once sent. Reads go through `visible()` for the caller.

## A client's withdrawal, the requests side (P-06-T19; ADR-162)
`service.withdraw_upload(tx, …)` runs inside evidence's withdrawal unit of work. It voids the version's fulfilments of the items the client may withdraw from, audits `fulfilment.withdrawn` and `request_item.upload_withdrawn` (identifiers only, never the file name), and returns to `requested` each item the version was the only fulfilment of.

## Questionnaires (T-02-T16, T-02-T22; `questionnaires.md`, live)

Organizer templates import as CSV (`questionnaire_templates.py`; markup, formulas and template
expressions refused, dry run first) and publish as versions; a questionnaire attaches a version to
a binder (`questionnaires.py`); the portal reads and autosaves answers optimistically
(`portal_questionnaires.py`, `If-Match`, 409 on a stale version). A question a person adds is a
draft until sent and never reaches the portal; an inquiry lists only for its addressee. Answers
are client content: stored and served verbatim, never interpreted (ADR-052).

## Not built (P-06 close-out, 2026-10-26)
- `PUT /v1/binders/{id}/follow-up-override` still answers 501: the column exists and `BinderOut` carries it, but nothing writes it.
- The OQ-1 preparer path (DEC-136): `binder.publish` on a `tax_return` binder has DEC-38's cells only, so the return's preparer cannot publish on the live stack.
- `requests.api.awaiting_review_count` (P-06 §2.3, for I-01) does not exist.
