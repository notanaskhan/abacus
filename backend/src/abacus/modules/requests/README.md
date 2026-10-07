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
