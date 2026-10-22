---
id: TASK-419
title: Migration 0100 binder_engine - binder stamps and recipients, request fields, delegations, upload intents, binder activity (P-06-T05)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T05
branch: p06-t05-binder-engine
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Upgrade and downgrade pass on the synthetic seed; a sent request cannot be soft-deleted (CHECK)."

## Plan
- Migration 0100, following P-06 §4.2.
- `requests/registry.py` and the schema_check expectations.
- Regenerated isolation tests.
- Rollback: `alembic downgrade 0099`.

## What changed
- **`request_lists`:**
  - unpublish stamps with a sealed reason;
  - `created_from` and `template_ref`;
  - `follow_up_override` (every 1–30 days, at most 4);
  - close stamps.
  - The app may update the stamps only.
- **`binder_recipients`:** new and insert-only; a removal is a new row with `removed_at`.
- **`request_categories`:** gain `glyph` and `family`.
- **`request_items`:**
  - `title`, `category_id`, `firm_owner_user_id`, the period (start ≤ end), `wave`, `kind` (default `client_upload`), `source_tag`, `supports_ref` and `linked_ref`;
  - drafted-wording provenance: the run, the source (template or model) and the fingerprint are all set or all null;
  - `sent_by`;
  - a soft delete. `request_items_only_unsent_drafts_deleted` allows `deleted_at` only on a draft never sent.
- **`request_delegations`:** new; the app may update only `revoked_at`.
- **`request_upload_intents`:** new and UNLOGGED, with a 90-second TTL. Swept, and never authoritative.
- **`binder_activity`:** a new projection, indexed by work item and status, and by status and last client activity.
- All the new tables have forced RLS.

## Progress log
- 2026-10-22: ran `test_schema_check_db` (up, down and up) and the request integration tests against 0100.
- 2026-10-22: the row also names `seed_dev.py`. Turning `binders.engine` on for the local firm waits for the flag from the C5 stub (P-06-T01).
