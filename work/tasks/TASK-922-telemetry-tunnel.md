---
id: TASK-922
title: Browser error tunnel POST /v1/telemetry/errors with allowlist rebuild (Q-01-T48)
spec: SPEC-050
acceptance_criteria: [AC-17]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T48
branch: q01-t48-telemetry-tunnel
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A seeded SSN, TIN or email in a browser event never reaches the forwarded Sentry payload, and agent, support-session and unauthenticated calls are refused" (Q-01-T48; Q-01 §3).

## What changed
- `platform/telemetry.py` rebuilds every event from an allowlist:
  - from the browser, only the error's type name and the route template, each refused unless it matches a strict, digit-free shape;
  - from the server, the environment, the release and the tenant UUID;
  - messages, values, frames, breadcrumbs, users, URLs and request data are dropped.
- Limits: 64 KB per envelope (413) and 30 per minute per person (429).
- `kernel.error_tracking.forward_event` scrubs again on the way out and is a no-op when tracking is off.
- Tests: `tests/integration/test_telemetry_tunnel.py` (8).

## Decision
- The route uses the `OWN` marker (any signed-in member, client users included, never a support session), not a new `telemetry.error.report` matrix action. Under ADR-027's matrix, a firm-level non-read action denies a member with no firm role and no engagement, and the plan wants every human principal to be able to report.
- INV-1 still holds: the agent principal holds no telemetry action, and agents never reach HTTP.

## Not done
- The browser half: Q-01-T50, in progress in parallel.
- Independent tests: Q-01-T59.

## Progress log
- 2026-10-23: the tunnel tests, the route introspection suite and the app gates pass.
