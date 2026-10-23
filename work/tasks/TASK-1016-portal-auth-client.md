---
id: TASK-1016
title: Portal auth client app-core/auth/bff.ts - in-memory token, refresh through the host cookie, 401 to sign-in with return, sign-out; POR-01 on the generated client (P-08-T11)
spec: SPEC-320
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
epic: P-08
plan_key: P-08-T11
branch: s6-portal-auth-client
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"An expired access token refreshes silently once, a failed refresh lands on /sign-in with the
return path, and no token touches localStorage or sessionStorage" (P-08-T11). The client half of
ADR-168 and DEC-212 (P-08-T10's BFF), copying the staff client (P-01-T11, TASK-945).

## Plan (amber: written before the build)
- **Files.** New `apps/web/src/app-core/auth/bff.ts`: the portal access token in module memory
  only (`{token, expiresAt}`), `setPortalSession` (verify's answer), `refreshPortalSession`
  (`portalRefresh` with `X-Abacus-CSRF: 1`; the browser sends the `__Host-abacus-portal` cookie and
  its own Origin; one in flight, so concurrent callers share the rotating cookie once),
  `freshPortalToken` (refresh 30 s before expiry), `ensurePortalSession`, `handlePortalUnauthorised`
  (refresh only if the failed request carried the token still held, else reuse the newer one; on
  failure go to `/sign-in?return=<path+query>`, never the fragment), `portalSignOut`
  (`POST /v1/portal/auth/sign-out` with the bearer, then forget it, even when the call fails),
  `safePortalReturn` (same-origin path, not `/sign-in`, not `/v1/`), and `configurePortalClient`
  (the generated client's interceptors: bearer on every non-pre-session call, refresh-then-replay
  once for a 401 on a request without a body; the pre-session family `/v1/portal/auth/*` is never
  refreshed or replayed, so a wrong code's 401 stays the screen's).
  `app-core/portal-session.ts` keeps `LANDING_PATH` and re-exports the token accessors from bff.ts
  (so the domain and screens keep their imports). `entries/portal.tsx` calls
  `configurePortalClient`. `routes/portal/index.tsx`: a signed-in area waits for
  `ensurePortalSession` (a reload refreshes from the cookie) instead of trusting fixture mode; the
  sign-in page returns to a safe `?return=` before the role landing; the sign-in navigator is the
  router's history.
- **POR-01 on the generated client.** `domain/portal/sign-in.ts` calls `portalStart`,
  `portalVerify` and `portalResend`; `portal-contracts.ts` re-exports the generated pre-session
  types in place of its drafts (branding and links/renew stay as they are: P-08-T05's and T21's).
  The screen hands verify's answer to `setPortalSession`.
- **Fixtures.** `fixtures/handlers/portal.ts` answers `POST /v1/portal/auth/refresh` (the
  persona's fixture cookie: a token for a persona with a portal shell, else 401
  `session_expired`) and `POST /v1/portal/auth/sign-out`.
- **CSP.** The portal build already uses the shared `abacus-csp` plugin (`connect-src 'self'`); a
  test pins that the plugin is not mode-gated and that bff.ts calls only same-origin paths.
- **No registry, flag, migration or OpenAPI change.** Backend untouched.
- **Tests (first).** `app-core/auth/bff.test.ts`: refresh once with the CSRF header and no bearer;
  parallel 401s share one refresh; a stale 401 after a refresh reuses the new token; a GET replays
  once; a second 401 on the replay does not refresh again; a failed refresh lands on
  `/sign-in?return=` with path and query and never the fragment; unsafe returns refused; sign-out
  sends the bearer and clears memory even on failure; a wrong code's 401 is not a session ending;
  `Storage.prototype.setItem` is never called and web storage holds no token through the whole
  flow; the CSP pin. POR-01's suite stays green on the generated calls.
- **Rollback.** Revert the commit: the portal goes back to an unrefreshed in-memory token.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built as planned. `bff.ts` plus `bff.test.ts` (20 cases) and `bff.csp.test.ts` (2);
  POR-01's suite unchanged and green on `portalStart`/`portalVerify`/`portalResend`. `bff.ts`
  joins `LEGACY_CLOCK` in eslint (token lifetime on the device clock, as `session.ts`; recorded in
  packages/ui/src/tokens/DECISIONS.md). Portal initial bundle 105.7 to 106.6 KB of 150 KB; the
  portal dist check is clean; J12 1 and 2-3 pass on the fixture project. Not built: a sign-out
  control (the portal has no account menu yet); the backend is unchanged.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-231 | Return parameter name, replay and refresh rules, fixture cookie | No (ADR-168, DEC-212) |
