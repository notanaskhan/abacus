---
id: ADR-168
title: Portal sessions - opaque access tokens checked against auth_sessions, pinned to the tenant and host they were minted on, after the portal's own email code (an exception to ADR-020 for portal clients)
status: accepted
date: 2026-10-23
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-020 buys authentication and owns authorisation. For staff that holds: WorkOS AuthKit signs them in and issues the tokens the API verifies (ADR-141, ADR-165). Portal clients can't follow the same path. WorkOS Magic Auth always emails its own branded code and can't be told not to, so the portal issues its own sign-in codes (DEC-155, the P-08 R1 fallback). When our code verifies, no provider has authenticated the client, and nothing bought can issue the session the portal needs. WorkOS still holds the client's user record and their TOTP factor, and the second step verifies through it.

## Decision
For portal clients only, the BFF issues the session itself.
1. **An opaque access token.** When the email code (and the WorkOS TOTP, when the client's role needs MFA) verifies, the BFF mints a random 256-bit access token. It is returned once in `PortalSignInVerifyOut` and kept in memory by the SPA (P-08-T11). It is not a JWT, carries no claims, and is stored only as its SHA-256.
2. **Checked against `auth_sessions` on every request.** A portal session row holds the token's hash, its expiry (15 minutes), the user, the tenant and the host it was minted on. The API resolves a bearer that isn't a provider token by that hash, with a short in-process cache. Revocation is immediate: ending the session ends the token.
3. **Pinned to its tenant and host.** A portal token presented on another firm's portal host, or on the firm app's host, is answered exactly as no session (401 `unauthenticated`). Authorisation still comes only from the session's membership and client access grants, never from the host (ADR-163 §5).
4. **Refresh like staff.** A `__Host-` cookie, stored as a SHA-256 and rotated on every refresh with reuse detection, and the `X-Abacus-CSRF` header plus an Origin check, mint a new access token (ADR-165's pattern, idle and absolute limits from DEC-140).
5. **Nothing else is built.** Staff authentication, SSO, SCIM and MFA factors stay bought (ADR-020, ADR-141). The portal builds only the code check (DEC-155) and this session.

## Options considered
### Option A: opaque session token checked per request — chosen
- Pros: no signing keys, rotation or JWKS to keep; revocation is immediate; the token says nothing if it leaks into a log.
- Cons: one indexed lookup per portal request (cached briefly); the session store must be available.

### Option B: self-signed JWT as a second issuer
- Pros: stateless per request; the same shape as the staff path.
- Cons: signing-key custody, rotation and a JWKS for a second issuer; a revoked session stays usable until the token expires.
- Rejected.

### Option C: hold portal sign-in until WorkOS can suppress its email
- Pros: no exception to ADR-020.
- Cons: the portal journey (J12) and the portal auth client stay blocked with no date.
- Rejected.

## Consequences
- The authentication dependency resolves two kinds of bearer: provider tokens (staff, verified as today) and portal session tokens (looked up). A portal token never authenticates a staff route's principal, and a staff token is refused on a portal host.
- Portal sessions live in `auth_sessions` with a `surface` column, behind the same definers as staff sessions.
- `test_portal_host_pinning.py` is binding: the host changes branding only, and another host is no session.

## Enforcement
- [ ] Test: a portal token on another firm's host or the firm app host gets 401 `unauthenticated`.
- [ ] Test: a revoked or expired portal session's token gets 401 at once.
- [ ] Test: the token is stored only as a SHA-256, and no log line carries a token or a code.

## Guidance for agents
Never add claims to a portal token, never verify it as a JWT, and never let a host decide anything but branding. Session reads and writes go through identity's definers.

## Revisit when
WorkOS offers a way to authenticate a user after our own code check without sending its email, or portal traffic makes the per-request lookup a measurable cost.

## Related
ADR-020, ADR-141, ADR-163, ADR-165; DEC-140, DEC-155; P-08 R1.
