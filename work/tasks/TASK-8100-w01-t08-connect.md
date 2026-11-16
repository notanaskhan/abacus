---
id: TASK-8100
title: W-01-T08 Connect, reconnect, disconnect — PKCE state, firm-app enable and disable, typed-name disconnect, secret erasure, remote revoke, membership-end revocation
spec: SPEC-659
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-24, AC-25, AC-26]
risk_zone: red
status: in-review
branch: w01-t08-connect
created: 2026-11-15
updated: 2026-11-15
---

## Objective
The Connect write path behind WB-10's Enable and WB-11's Reconnect and Disconnect (DEC-5074).

## Plan (red)
- `integrations/connect_service.py`: start (firm, personal), complete, disconnect (firm, personal), `membership.deactivated` handler; `connect_errors.py`; personal-install secrets in `secrets.py`.
- Routes wired in `connect_contract.py`; integrations declares `SUBSCRIPTIONS` (the worker hosts it).
- Audit: `user_integration` target (firm level); the new actions in `activity_reviewed.py`.
- Client regenerated (route errors).
- Rollback: the routes return to the 501 stub; no migration.

## Partly built
- OQ-5's suspension: built in TASK-8112 (0902, DEC-5083) with `needs_attention` + `firm_app_disabled`, no new status.
- AC-14's Aug 17 replay and AC-27 to AC-30 (health monitor, admission) are W-01-T13 and later.

## Progress log
- 2026-11-15: built; `tests/integration/test_w01t08_connect.py` (9) green; the W-01 AC suite's AC-4, AC-12, AC-26 strict xfails removed (they pass). AC-7's "both admins reach connect" needs the catalogue content in the security database: W-01-T10.
- 2026-11-16: AC-25 suspension and the POR-16 firm-app refusal built in TASK-8112 (#2115).
