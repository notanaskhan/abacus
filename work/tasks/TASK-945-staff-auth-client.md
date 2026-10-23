---
id: TASK-945
title: Staff auth client in app-core/auth, SHL-06g and the sign-in error state (P-01-T11)
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: P-01
plan_key: P-01-T11
branch: TASK-945-staff-auth-client
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"No token is kept in web storage, an expired session returns to the same route and SHL-06g passes
Tier C" (P-01-T11). P-01 AC 5.1.3 to 5.1.6 on the client side of the staff session BFF
(P-01-T09, ADR-165). SPEC-000 AC-1: a member signs in through the identity provider and lands in
the firm.

## Plan (amber: written before the build)
- **Files.** New `apps/web/src/app-core/auth/{session.ts, use-signed-in.ts, index.ts}`: the
  in-memory token, `refreshSession` (`POST /v1/auth/refresh` with `X-Abacus-CSRF: 1`, one in flight),
  `startSession` (the landing; starts the loop guard), `freshToken`, `ensureSession`,
  `handleUnauthorised` (refresh, else sign in with the current path and query), `signIn` (top-level
  navigation to `GET /v1/auth/sign-in?return_to=`, `reauthenticate=true` for step-up), `signOut`
  (`POST /v1/auth/sign-out`) and `endSession`. `api.ts` interceptors: refresh before a request when
  the token is about to run out; on a 401, refresh once and replay a request without a body. The
  BFF's own routes are never intercepted that way.
- **Removed.** `apps/web/src/auth/{session,pkce}.ts` and their tests (the in-browser PKCE flow and
  the sessionStorage token), `legacy/SignInCallback.tsx`.
- **Screen.** `screens/SHL-06/` g, `error` and `expired` on fixture scenarios
  (`fixtures/scenarios/SHL-06.ts`), routed at `/signin/callback`; gallery
  `/components/screens/SHL-06?st=g|error|expired`. `AuthCard` gains a neutral `brand="marks"` slot
  so the firm sign-in can draw the Accrued wordmark and monogram while the portal kit never names
  the product.
- **CSP.** `connect-src 'self'` (AC 5.1.6); the IdP authority env (`VITE_OIDC_*`) is gone.
- **Local dev.** `make dev` sets the BFF's `ABACUS_IDENTITY_CLIENT_ID`, `…_AUTHORIZE_URL`,
  `…_EXCHANGE_URL` and `ABACUS_WEB_ORIGIN` for the fake sign-in server, which already accepts
  `/v1/auth/callback`. `make dev-fixtures` answers the refresh with a fixture word.
- **No backend, contract or migration change.**
- **Rollback.** Revert the commit: the BFF routes stay and the old flow returns.

## What changed
- As planned. Callers moved: `legacy/{Layout, ClientHome, ClientEngagement, ConnectCallback, Join,
  ClientAccept, Signup}.tsx` use `useSignedIn` (refresh first, then sign in);
  `shell/mfa.tsx` step-up uses `reauthenticate`. ESLint: the auth code lost its `fetch` exception
  and the wall-clock allowance moved to `app-core/auth/session.ts` (token lifetime).
- Manifest SHL-06 `live` (no area path: a redirect landing). Parity manifest `shl-06g.window`
  (Tier C). `e2e/screens/SHL-06.spec.ts` (axe). `docs/screens/SHL-06.md`, DEC-149,
  `docs/architecture/authkit-staff-sign-in.md`.

## Tests mapped to ACs
- AC 5.1.3 → `SHL-06g signing in` (refresh with CSRF, `/v1/me` with the in-memory bearer, safe
  return path), `SHL-06g opens only a same-origin return path`.
- AC 5.1.4 → `an expired session returns the person to the same route`,
  `replays a GET once with the refreshed token after a 401`, `refreshes before a request when the
  token is about to run out`, `SHL-06g returns to the route the session expired on, query
  included`, `Layout … redirects to sign-in` (`return_to=%2Fengagements%2Fe1`).
- AC 5.1.5 → `holds the BFF's token in memory only`, `SHL-06g keeps no token in web storage`,
  `asks for a fresh sign-in for step-up`.
- AC 5.1.6 → `fonts.test.ts` and `e2e/ds-fonts.spec.ts` policy (`connect-src 'self'`).
- AC 2.1.6 → `ends the BFF session with the bearer token, then forgets it here`.
- SHL-06g Tier C → parity `shl-06g.window` 0.23 % locally (threshold 3 %).

## Progress log
- `2026-10-23 13:40` — Built and green: apps/web typecheck (no new errors), lint, vitest
  113 files / 1107 tests; packages/ui auth-card tests; Playwright `e2e/screens/SHL-06.spec.ts` 3/3
  with axe; parity `shl-06g.window` passes Tier C locally at 0.23 %.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| g keeps the card geometry with frame 1's title, no code boxes (DEV-2, DEC-149) | Nothing is typed in the product after the hosted pages | no |
| Error copy per BFF code (DEC-149) | The state is undesigned; T15 error grammar | no |
| Only body-less requests are replayed after a refresh | A sent body cannot be read again without buffering every upload | no |
| `AuthCard brand="marks"` instead of an Accrued variant | The portal kit's lint forbids the product name (DEC-59, INV-4) | no |

## Gotchas and discoveries
- **First sign-in gap (stopped, not worked around):** the BFF refuses a provider subject with no
  user row (`unknown_staff_user`), so self-serve sign-up and invitation acceptance for a brand-new
  person reach the error state. Needs identity's BFF change (P-08-T10 for clients, a P-01-T09
  follow-up for staff). Recorded in `docs/screens/SHL-06.md` Open gaps and DEC-149.
- The portal pages under `/client` share this client until P-08-T11.

## Handoff
- **Current state:** done.
- **Exact next step:** P-01-T15 (independent AC tests), P-01-T16 (Tier C lock for SHL-06g,
  journeys on staging).
