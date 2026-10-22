---
id: TASK-406
title: Notifications catalogue v2 - kind registry, read-time facts and pending, feed with tabs and counts (P-01-T06)
spec: SPEC-013
acceptance_criteria: [AC-1, AC-5]
risk_zone: amber
status: done
epic: P-01
plan_key: P-01-T06
branch: p01-t06-catalogue-v2
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Live E0 rows d, e and g resolve with facts, walled rows vanish, and no row stores text."

## Plan
- `notifications/kinds.py`, the slot.
- Catalogue registrations, the fan-out changes, `feed()`, and the live `/v1/notifications/feed` behind `notifications.v2`.
- No migration (0090 holds the columns).
- Rollback: revert the commit. Turning the flag off hides the feed.

## What changed
- **`register_kind(NotificationKind(code, category, glyph, email_default, inline_actions, facts, pending))`:**
  - fails at startup for a new dotted code, a second registration of a code, an inline action outside the closed set, or any inline action on an agent kind;
  - the 17 SPEC-013 kinds register through it, the three renamed codes among them;
  - exported from `notifications.api` with `kind_of` and `registered`.
- **Fan-out:**
  - an unregistered kind is dropped and counted (`abacus.notifications.dropped`);
  - recipients walled from the engagement's client get no row (INV-3);
  - rows store `category`, `actor_user_id`/`actor_kind`, `client_id` and `work_item_id`, and still no text.
- **`feed(ctx, tab, cursor, limit, days)`:**
  - the caller's own rows in the last 30 days of business time, walls applied at read time;
  - `pending` and `facts` resolve now through each kind's resolvers;
  - tabs: all, approvals (pending rows), mentions, client activity;
  - counts: pending approvals, plus unread mentions and unread client activity;
  - sealed keyset cursors and a 500-row window.
- **`GET /v1/notifications/feed`** is live behind `notifications.v2` (404 when off). Preferences stay a 501 stub until P-01-T12.

## Progress log
- 2026-10-22: built per the S3 batch rules. The new `tests/unit/notifications/test_kinds.py` covers the C16 rules, every code passing the 0090 CHECK, and the tab categories.
- 2026-10-22: no SPEC-013 kind has a facts resolver yet. Rows d, e and g (`client_uploaded`, `mention`) list with empty `facts` until evidence and requests register their resolvers through `notifications.api`; the live facts are wired in P-01-T16. `SUBSCRIPTIONS` is still computed when `notifications.api` is imported, so `register_kind_source` (the next kind source) has to land with a subscription refresh.
- 2026-10-22: fixed `validate_docs` on TASK-391 to TASK-401 by using spec AC ids instead of plan story ids.
