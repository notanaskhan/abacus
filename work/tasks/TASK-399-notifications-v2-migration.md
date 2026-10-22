---
id: TASK-399
title: Migration 0090 notifications v2 (P-01-T03)
spec: SPEC-013
acceptance_criteria: [C16]
risk_zone: amber
status: done
epic: P-01
plan_key: P-01-T03
branch: p01-t03-notifications-v2
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"up/down/up passes, the backfilled undotted codes pass the widened CHECK, RLS is forced on both
new tables, and the existing notification tests still pass."

## Plan
- Migration `0090_notifications_v2`, plus the notifications registry rows.
- The catalogue's stored codes for the three renamed kinds.
- The SPA kind maps.
- No flag edits. Rollback: `alembic downgrade 0089`, which maps the three codes back and restores the dotted-only CHECK.

## What changed
- **Kind CHECK:** dropped and re-created as `^[a-z][a-z_]*(\.[a-z][a-z_]*)?$`, NOT VALID then validated, before the backfill.
- **Renames, with backfill:** `evidence.uploaded`→`client_uploaded`, `comment.mentioned`→`mention`, `review.assigned`→`review_assigned`. The catalogue now stores these codes. Its keys are still the event types.
- **New columns on `notifications`:**
  - `category`, backfilled from each kind. Approval covers review, the partner decisions, independence and drafted reminders; client activity covers uploads and connections; system covers support and budget; everything else is other.
  - `actor_user_id`, `actor_kind`, `client_id` and `work_item_id`. The app may insert them.
- **Index:** the recipient index gains `id`.
- **`notification_preferences`:** PK `(tenant, user, kind)`, the kind CHECK, an FK to memberships. The app updates only `in_app`, `email` and `updated_at`.
- **`notification_deliveries`:** `UNIQUE (notification_id, channel)`, email only, a closed status set. It cascades on the notifications purge. The app updates only `status` and `message_ref`.
- Both new tables are tenant tables with forced RLS. `updated_at` and `created_at` default to `abacus_now()`.
- **SPA:** `shell/notifications.ts` and the drawer and legacy tests use the new codes.

## Progress log
- 2026-10-22: ruff and pyright are clean. The drawer and legacy vitest files pass. The notification integration tests run against the migration, since the fixture migrates up, down and up.
