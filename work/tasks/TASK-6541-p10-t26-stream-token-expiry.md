---
id: TASK-6541
title: "P-10-T26 finish: streams close 30 seconds before the access token expires"
spec: P-10
acceptance_criteria: [close-before-expiry]
risk_zone: red
status: in-review
branch: s33r-p10-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T26
---

## Objective
`kernel.realtime.stream` already closes `CLOSE_BEFORE_EXPIRY_SECONDS` before `expires_at`, but
every caller passed None. The firm app's access token expiry now reaches the run, badge and
`/v1/events` streams.

## Plan (red)
- `identity.tokens.VerifiedIdentity.expires_at` from the verified `exp` (not compared: identity
  equality unchanged).
- `kernel.request_context`: `token_expires_at` on the request context, set by `note_session`
  from `identity.routing.current_context`; `token_expires_at()` reads it.
- `agents/run_stream.py` (run and badge streams) and `notifications/realtime.events_stream` read
  it before the body runs and pass it to `realtime.stream`.
- Tests: `tests/unit/kernel/test_s33r_p10t26_token_expiry.py`; `test_tokens.py` inventory gains
  `expires_at` and an expiry test.
Rollback: revert (streams then run until re-auth fails, as before).

## Left partial
- Portal sessions: `portal_invitee_resolve` returns no `access_expires_at`; a portal stream still
  closes on re-auth (60 s) only. Needs a migration changing the definer function's return type.

## Progress log
- `2026-11-10` — Built; unit tests pass (109 with the token suite). Gates at the end.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3141 | The access token's expiry travels on the request context to the streams | no |
