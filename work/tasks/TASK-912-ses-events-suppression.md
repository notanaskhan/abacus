---
id: TASK-912
title: SES delivery events and per-firm email suppression (Q-01-T46)
spec: SPEC-319
acceptance_criteria: [AC-6]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T46
branch: q01-t46-ses-events
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"SES simulator bounce and complaint create delivery rows and suppress the next send to that address hash, with no clear-text address in events or logs" (Q-01-T46; Q-01 §4.2).

## Plan
- Migration `0104_message_deliveries`:
  - `message_deliveries`: insert-only, with immutable triggers, unique on `provider_event_id`;
  - `email_suppressions`: HMAC address hashes, one live row per address, lift by stamp.
- `communications/deliveries.py`:
  - `parse_ses_event` reads the EventBridge envelope and matches by the `tenant_id` and `message_id` tags;
  - `record_ses_event` records each event idempotently, suppresses on a permanent bounce or a complaint, and emits `message.bounced` or `message.complained`;
  - `send_email` refuses a suppressed address;
  - `drain_ses_events` works over an `SesEventQueue` port, with SQS behind it.
- `communications/workflows.py`: `DrainSesEventsWorkflow`, registered as `time_sensitive`.
- The three send paths (client invitation, staff invitation, follow-up) go through `send_email`. A suppressed send is recorded `blocked` with the violation `suppressed`.
- Settings: `ses_events_queue_url` and `email_suppression_pepper` (a SecretStr; local and test runs use a fixed pepper).
- Rollback: downgrade 0104. The send paths then fail at `is_suppressed`, so revert the code as well.

## What changed
- As planned. Tests are in `tests/integration/test_message_deliveries.py` (16).
- Deviation: `messages.provider_message_id` is not added. `messages` is insert-only, and events already match by the `message_id` tag, so the provider id is never needed.
- Deviation: `message_deliveries.message_id` has no foreign key. A staff invitation's send records no message, and its delivery events are still kept.
- **Fixes for other S4 merges on main:**
  - `test_schema_check_db` update-column expectations (P-07-T07, P-04-T10);
  - audit target placement for `auth_session` (firm-level) and `approval_grant` (engagement or firm);
  - the fake sign-in server's redirect test (P-01-T09);
  - the P-08 portal flags' expiry (renewed to 2027-04-21 under DEC-137);
  - a `single_audit` allowlist entry for P-07-T06's consumer test;
  - a secrets-scan ALLOW for screenshot digests in the parity manifest;
  - a TOTP-shaped literal removed from the portal contract test;
  - a duplicate TASK-911 renumbered to TASK-913.

## Not done (infra and operations)
- The configuration set's EventBridge rule and SQS queue, the Temporal Schedule (`ses_events:platform`, every minute), and the bounce and complaint rate alarms. These are Terraform, and no session runs `terraform apply`.
- The SES mailbox-simulator run on staging.
- The workflow's replay history, which gets recorded once the Schedule exists.

## Progress log
- 2026-10-23: the deliveries tests, the full `test_schema_check_db` and the unit suites pass.
