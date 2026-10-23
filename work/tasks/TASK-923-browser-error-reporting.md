---
id: TASK-923
title: Browser error reporting through the tunnel, and the platform error copy (Q-01-T50)
spec: SPEC-050
acceptance_criteria: [AC-16, AC-31]
risk_zone: amber
status: done
epic: Q-01
plan_key: Q-01-T50
branch: TASK-923-browser-error-reporting
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A thrown error in the staging SPA reaches Sentry with route template and release only, and the three error codes show their mapped copy" (Q-01-T50; Q-01 sections 3 F6 and 5).

SPEC-050 has no AC written for T50. The nearest are AC-31, the runtime config this reads, and AC-16, the retryable `unscannable` state whose copy this adds.

## Plan
- `apps/web/src/app-core/runtime-config.ts` (new): the typed schema of `docs/contracts/platform-ops.md` section 3.2 with a parser and a loader. A missing or invalid file answers null.
  - Q-01-T23 still has to make the file required before router boot (the plain error state) and move the OIDC authority and client ID onto it.
- Contract: `sentry.tunnel` is added in place as an optional key. It is an additive change, which the contract allows in place.
  - Reporting is on only when both the DSN and a same-origin tunnel path are present. Events never go to the ingest directly, which keeps CSP `connect-src 'self'`.
- `apps/web/src/app-core/telemetry.ts` (new): `@sentry/browser` with an allowlist `beforeSend`. The event is rebuilt from:
  - the error type, mechanism and frames (path only, with no origin, query or fragment);
  - the route template as the `route` tag;
  - release, environment, event ID, timestamp, level and platform.
- The allowlist drops the message and exception value, user, breadcrumbs, request, extra, contexts and fingerprint. It also drops events below `error` and events with no exception.
- SDK settings: `defaultIntegrations: false` (only GlobalHandlers, LinkedErrors and Dedupe), `maxBreadcrumbs: 0`, `beforeBreadcrumb` returning null, `dataCollection` all off and no client reports.
- Transport: posts the envelope to the tunnel path with the session's bearer and firm headers. With no signed-in session it sends nothing, so errors before sign-in are not reported (plan Q1).
- `main.tsx` loads the runtime config. The SDK is a lazy chunk imported only when reporting is configured, so the firm entry budget is unchanged in kind (telemetry is a 31 KB route chunk).
- `api.ts`:
  - `sessionHeaders()`;
  - message-map entries for `read_only` (the plan's copy, verbatim), `service_unavailable` (also today's 503 body `service unavailable`) and `unscannable`.
- ESLint: `fetch` is allowed in the two new app-core files. One is a static file, not the API. The other is a Sentry envelope, not a JSON body.
  - The generated `browserError` operation has `body?: never`, and its interceptor's 401 handling would sign the person out over a telemetry post.
- Rollback: revert the commit. With no `sentry.tunnel` in a host's runtime config, nothing is sent.

## What changed
- As planned. Tests:
  - `app-core/telemetry.test.ts` (8): the real SDK runs with `fetch` stubbed, so no route is needed. A thrown error carrying a seeded email, SSN, TIN, page text and URL query reaches the tunnel with the route template, release and environment and none of those values. There are no `user`, `breadcrumbs`, `request`, `extra`, `contexts` or `message` keys. Bare messages and signed-out sessions send nothing.
  - `app-core/runtime-config.test.ts` (6): the contract example, unknown keys, missing and malformed files, and same-origin tunnel enforcement.
  - `api.test.ts`: the copy for the three codes.
- The Q-01-T48 tunnel (TASK-922) landed while this was in progress. The browser event already carries what it reads: `exception.values[-1].type` and `tags.route`, and TanStack `fullPath` templates fit its route shape.

## Copy
- `read_only`: "This workspace is read-only for maintenance. Changes are paused." (the epic's copy, verbatim).
- `service_unavailable`: "This isn't available right now. Try again in a few minutes."
- `unscannable`: "We couldn't check this file just now, so nothing was saved. Try uploading it again."
- The last two are inferred, in the style of the existing upload refusals, with no new terms. They never say "Accrued", because the portal shows them too. The backend still answers a scanner refusal as `file_refused`, so `unscannable` copy shows once the upload route sends that code.

## Progress log
- 2026-10-23: vitest on the touched files (70) and the full web suite pass. ESLint (whole app), prettier and tsc pass, with no errors beyond the known `api-client` `*.gen.ts` set. The bundle budget passes (firm initial 242.4 of 250 KB; the telemetry chunk is 31.2 KB). `make check-generated` and `scope_guards` pass.
- `secrets_scan` reports one finding that is already on `main`: `backend/tests/integration/test_telemetry_tunnel.py:24` (PII-001, SSN `123-45-6789` from TASK-922). This change adds no finding: its test SSN is in the never-issued 9xx area.
