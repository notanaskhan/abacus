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
