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
