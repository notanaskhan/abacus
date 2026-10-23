---
id: TASK-953
title: Notification preferences API and the email channel; C16 v1 recorded frozen (P-01-T12)
spec: SPEC-013
acceptance_criteria: [AC-1, AC-7]
risk_zone: amber
status: done
epic: P-01
plan_key: P-01-T12
branch: TASK-953-notification-email
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A mention emails Hannah exactly once on the sink with no Restricted fact and C16 v1 is recorded frozen."

## Plan (amber: written before the code)
- **Files:**
  - `notifications/workflows.py` (new): `NotificationEmailWorkflow` and its inputs.
  - `notifications/email.py` (new): the fan-out delivery rows, the start through `kernel.dispatch`, and the send and record activities.
  - `notifications/service.py`: `notify` calls the channel; preferences; the feed hides in-app-off kinds.
  - `notifications/repository.py`: the preferences and deliveries tables.
  - `notifications/contract.py`: the live preference routes.
  - `communications/notification_email.py` (new): the C16 render and `send_email`.
  - `abacus_tools/workflows/record_notification_email.py` (new).
  - `abacus_tools/contracts.py`: `c16_notifications`.
- **Migrations:** none. `notification_preferences` and `notification_deliveries` came with 0090 and the templates with 0092.
- **Registry and flags:**
  - `notifications` may import `communications` (`MODULE_DEPENDENCIES` and its test).
  - `notifications.email` is the kill switch (it already exists).
  - New 422 code `unknown_notification_kind` (`error-codes.yaml` rebuilt).
- **Tests:**
  - `tests/integration/test_notification_email.py` (8; real Temporal for the end-to-end mention);
  - `tests/workflows/test_notification_email_replay.py` (histories v1 sent and failed);
  - `tests/contracts/c16_notifications/test_c16_frozen.py`.
- **Rollback:** revert the commit. With `notifications.email` off nothing sends, and the preferences answer from defaults.

## Decisions
DEC-152.

## Deferred
- The `notification.mention` template content is a staff import on each environment (database content), not part of this change.
- P-01-T14 writes the independent AC suite for this work.

## Progress log
- 2026-10-23: built with F-04-T22/T23 in one PR. All of these pass:
  - the integration suite, including Margaret's mention reaching Hannah once on the sink through Temporal and a redelivered event sending nothing;
  - the replay test and the C16 frozen-snapshot tests;
  - the unit, contract and security suites, ruff, pyright, `lint-imports`, `banned_patterns`, `secrets_scan`, `error_codes` and `make check-generated`.
- `2026-10-23` — P-01-T14 independent AC suite (TASK-993): ED-014 fixed (notification email is staff only).
