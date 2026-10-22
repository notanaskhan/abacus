---
id: TASK-408
title: Migration 0093 review_core - sign-offs, review notes, field value versions, human gates (P-04-T03)
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T03
branch: p04-t03-review-core
created: 2026-10-22
updated: 2026-10-22
---

## Objective
P-04-T03: sign_offs (level, kind, content_hash, a human-only CHECK bound to the app.actor GUCs), review notes and their events, field_value_versions (the policy source blocked by `fvv_policy_dormant`), and the human_gates projection. Owners and insert-only lists in `review/registry.py`. Up/down/up passes.

## Plan
- Migration 0093 (DEC-134: extend the SPEC-308 and SPEC-313 tables, don't rename them).
- `review/registry.py` and the schema_check immutable list, with their test expectations.
- Regenerated isolation tests.
- Rollback: `alembic downgrade 0092`.

## What changed
- **`sign_offs`:**
  - new columns: `kind` (ladder, field_tick or final_approval; field ticks are L1/L2 only), `work_item_id`, `initials`, `engagement_role_at_sign`, `function_at_sign`, `version_no`, `statement_version`, `adopted_run_id`, `independence_checked_at` and `bulk_request_id`;
  - `actor_kind`/`actor_id` default to the transaction's actor, and the `sign_offs_human_only` CHECK requires a human matching the `app.actor_*` settings;
  - a time index.
- **`reviewable_notes`:**
  - `status` (open, responded, cleared, closed, withdrawn), backfilled from each note's latest event;
  - `assignee_user_id`, `anchor_ref` and `body_sealed`;
  - the app may update only status and assignee.
- **`reviewable_note_events`:** gains the `raised`, `closed` and `withdrawn` kinds and `actor_kind`. A cleared event must be a human's.
- **`field_value_versions` (new):**
  - insert-only for every role, enforced by triggers;
  - `fvv_policy_dormant` holds the policy source and actor off (DEC-53), and a human edit must carry a sealed citation note;
  - the actor must be the transaction's;
  - unique per target, field and seq.
- **`human_gates` (new projection):** the DF-25 kinds, open/done/voided, idempotent on `(tenant, source_event_id)`, with no app DELETE.

## Progress log
- 2026-10-22: ran `test_schema_check_db` (up, down, up and the contracts) and the review and workpaper integration tests against 0093.
