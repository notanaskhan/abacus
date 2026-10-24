---
id: TASK-1132
title: Independent AC tests (ADR-078) for the portal sign-in - branding, the provider port, the sign-in BFF and the auth client (P-08-T20)
spec: SPEC-320
acceptance_criteria: [AC-6, AC-7, AC-9]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T20
branch: s7-p08-invitations
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The suite is written in ayushkbhatia's session from the contract and SPEC and passes on main without edits by the implementing session." (P-08-T20 for T05, T06, T10, T11.)

## Plan (red zone)
- **Files:** `backend/tests/integration/test_p08t20_portal_sign_in_independent.py` (HTTP surface and the published service entry points only); `apps/web/src/app-core/auth/bff.independent.test.ts` (the generated client end to end with the interceptors). No production code, migration, registry or flag change.
- **Sources:** SPEC-320 AC-6, AC-7, AC-9; epic Stories 2.1 and 2.2; `docs/contracts/portal-identity.md` §2.2, §6, §7; ADR-168; the T11 row's acceptance. Not read for the cases: `test_portal_sign_in.py`, `bff.test.ts`.
- **Cases:** enumeration over valid, unknown, staff, another firm's and locked emails (status, key set, value types, no-store, median time ≥ 0.45 s and spread ≤ 0.35 s; one code request only for the valid client); no audit row for an unknown email; an unknown email locks the same way; the 10-minute code (410 after, accepted at 9:30); 2, 1 tries then 423 15 minutes ahead, refused on a fresh challenge, signed in after; resend 429 inside 60 s with the server's time, then 202, the old code void and the tries kept; the `__Host-` cookie's flags; refresh refused without the CSRF header, without Origin, with another Origin or a wrong header value, then rotated; refresh reuse ends the session; sign-out ends token and cookie; branding Public-only with the same keys for an unknown host, no identifier, logo 404; the in-memory adapter and the WorkOS fake give the same outcome sequence on the port; no email, IP, code, token or cookie in stdout, stderr or log records. FE: silent single refresh with the CSRF header and no bearer, parallel 401s share it, a failed refresh goes to `/sign-in?return=<path and query>` once (no fragment), a pre-session 401 is not refreshed, sign-out sends the bearer and forgets the token on failure, web storage never written.
- **Time:** security windows run on real time (`kernel.clock.system_now`, which a demo clock never moves, by design), so the suite stages time passing by moving the stored sign-in timestamps back; the row's "on kernel.clock" is read as "on the server's clock, never the browser's".
- **Rollback:** delete the two files.

## Progress log
- 2026-10-24: written from the sources above; 13 backend and 5 frontend tests pass on main unedited. Nothing found that contradicts the contract.
