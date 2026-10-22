---
id: TASK-384
title: /v1/me/capabilities and identity.allowed_actions; client_service cells (F-03-T30)
spec: SPEC-024
acceptance_criteria: [AC-5]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T30
branch: f03-t30-capabilities
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Grace Holloway's capabilities include binder and invitation actions but no evidence content
action, and the call records no authorisation check." (ADR-145, ADR-147)

## What changed
- `identity.allowed_actions(ctx, resource, candidates=None)`: every `authorise` layer except
  fresh MFA and a stated reason, in a probing mode that records no check, logs no denials and
  reads each engagement role once.
- Matrix: `client_service` (ADR-147) on `engagement.read_metadata`, `client_contact.invite/read/
  remove`, `request_item.read/create/update/assign`; never evidence or comment content.
- `GET /v1/me/capabilities?engagement_id=` (platform; action `self`): capabilities, role codes and
  labels, flags, entitlements, office, time zone, `mfa_recent_until`, `server_now`, `clock_mode`,
  and the portal shell and scopes for client users. Engagements registers
  `register_engagement_resource` so platform can build the engagement's `Resource`.
- `MemberFacts.office_id`; `identity.labels.ROLE_LABELS`. `/v1/me` itself already carries
  `server_now` and `clock_mode` (TASK-374).
- Tests: `tests/unit/identity/test_allowed_actions.py`.

## Progress log
- 2026-10-22: built. Tests run in the batch's end-of-run CI.
