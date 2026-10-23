---
id: TASK-932
title: Independent AC tests for the browser error tunnel POST /v1/telemetry/errors (Q-01-T59)
spec: SPEC-050
acceptance_criteria: [AC-24]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T59
branch: q01-t59-telemetry-tunnel-acceptance
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Tests … prove a seeded SSN, TIN or email is never forwarded, and agent, support-session and unauthenticated calls are refused" (Q-01-T59), written from Q-01 §3 F6 (the browser bullet) and §4 (the `POST /v1/telemetry/errors` row), not from TASK-922's code. SPEC-050 covers S0–S1 and has no telemetry AC yet; AC-24 (what answers without a token, body caps) is the nearest.

## What changed
- `backend/tests/integration/test_q01_telemetry_tunnel_acceptance.py` (36 tests, Postgres). Seeding goes through the shared `Seeder`.
- "Reaches Sentry" is observed at the wire. The real SDK is started through `configure_error_tracking` with a transport that keeps every serialised envelope. Nothing leaves the process.
- Allowlist:
  - Only the route template, error type, release, environment and tenant UUID come through.
  - Release, environment and tenant come from the server, never the browser.
  - Synthetic SSN, TIN (dashed and bare) and email values, plus a marker, are planted in every other field and in the envelope header. None of them reaches the wire, including when they are smuggled through the type or route (11 shapes).
  - Non-error items (session, transaction, attachment, client report) and message-only events are not forwarded.
- Principals:
  - Firm staff (four firm roles) and a client user with an `owner` grant may report.
  - Refused: unauthenticated callers (four header shapes), no membership, a revoked membership, a support-session header, a support principal, an agent principal and a system context.
- Limits:
  - An envelope of exactly 64 KB is accepted, and 64 KB + 1 byte is refused with 413.
  - A chunked oversized body and one with an understated Content-Length are also refused.
  - The 31st envelope in a minute is refused with 429. One person's limit does not use up another's.

## Findings
- No xfails: every AC outcome holds.
- The `OWN` choice (TASK-922) and INV-1:
  - A non-human principal that reaches the route (an agent or system context through the dependency override, as `tests/security/test_agent_principal.py` does) is refused. It gets a 500, though, not a 403. `current_member` reads `ctx.is_support`, and `AgentContext` and `SystemContext` have no such attribute, so the request fails with `AttributeError`. The server reports its own fault to Sentry; the browser's event is not forwarded.
  - The AC outcome (refused, nothing forwarded) holds, so the tests assert that.
  - With the plan's matrix action `telemetry.error.report`, `authorise` would refuse with a 403. If a deliberate refusal is wanted, `current_member` should reject anything that is not an `AuthContext`.
- The rate limit is kept per person (`user_id`), not per session as §4 says. That is stricter: two sessions of one person share 30 a minute. The tests cover one session and two different people.

## Progress log
- 2026-10-23: written from Q-01 §3 F6 and §4; 36 pass, three runs in a row, alongside TASK-922's own suite.
