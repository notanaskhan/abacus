---
id: ADR-165
title: Staff session BFF - the three pre-session /v1/auth routes on the ROUTE-001 exception list, a global auth_sessions store reached by definers, cookie rotation with reuse detection, 30-minute idle and 12-hour absolute limits
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
ADR-141 (P-54) puts staff refresh tokens in an httpOnly cookie behind a backend-for-frontend. A BFF cannot work without three routes that answer before any bearer token exists: `GET /v1/auth/sign-in`, `GET /v1/auth/callback` and `POST /v1/auth/refresh`. ADR-152 (P-45) lists `/healthz`, `/readyz` and portal branding as the only unauthenticated routes and says P-01 extends the list through its own ADR (P-01 open question Q1). ADR-030 requires an idle timeout and an absolute limit but sets no values. This ADR decides both for P-01-T09.

## Decision
- **Three pre-session routes on the ROUTE-001 exception list.** They stay inside `AbacusRouter` with the `PRE_SESSION` route marker, which the router accepts only for exactly these three paths. Each authenticates the request itself:
  - sign-in: none needed; it only starts a flow, storing server-side state and a PKCE verifier (10 minutes, single use);
  - callback: the single-use `state`, the PKCE verifier, and the provider's signed access token;
  - refresh: the session cookie, plus the `X-Abacus-CSRF: 1` header and an `Origin` equal to the app's own origin.
- **Sign-out is not pre-session.** It is `OWN` and needs the bearer token, and it ends only the caller's own session.
- **Sessions are global and reached only through SECURITY DEFINER functions.** A session spans memberships, so `auth_sessions`, `auth_session_cookies` and `auth_login_states` belong to no tenant. They have no privileges for the app or identity roles. They hold no tenant content. The provider refresh token is sealed with the platform key.
- **The cookie** is `__Host-abacus-session`: HttpOnly, Secure, SameSite=Strict, Path=/. It is stored only as a SHA-256 and rotates on every refresh. Presenting a rotated-out value ends the whole session (`reuse_detected`) and is audited as `session.refresh_reused`.
- **Limits (DEC-140):** 30 minutes idle and 12 hours absolute. Both are computed on each refresh from the session row; no workflow runs.
- **MFA at sign-in:** a session is refused unless the provider's token shows a second factor (`amr` contains `mfa`). This satisfies FTC Safeguards 314.4(c)(5) without trusting a vendor default. An SSO firm's IdP-enforced MFA attestation (G-02) may relax this later through its own ADR.

## Options considered
### Option A: pre-session marker inside `AbacusRouter`, paths pinned in code and on ROUTE-001 — chosen
- Pros: the routes keep the router's response-model and OpenAPI rules, and two protected lists name them.
- Cons: a second kind of exception beside `PUBLIC_ROUTES`.

### Option B: the routes outside `AbacusRouter` in `PUBLIC_ROUTES`
- Pros: one exception mechanism.
- Cons: `PUBLIC_ROUTES` is GET-only and out of the OpenAPI document. The refresh is a POST, and the generated client must type it.
- Why rejected: it would loosen the public-route rule for every entry.

### Option C: a tenant-scoped session table
- Pros: ordinary RLS.
- Cons: a person with two firms would need two sessions, and switching firms would need a new sign-in.
- Why rejected: a session belongs to a person, not to a firm.

## Consequences
**Positive**
- No token reaches web storage. A stolen cookie that has already been used is caught on its next use.

**Negative / costs accepted**
- Three more unauthenticated paths. Each is small and covered by its own tests.

**Follow-up work created**
- Code: P-01-T11 (the staff auth client); Q-01-T17 (the WorkOS adapter, with provider session revoke); P-08-T10 (portal BFF on the same pattern).
- Specs: SHL-06 (AC 5.1.2–5.1.5).
- Glossary: none.
- Matrix: none; the marker is the exception.
- Registry: `PUBLIC_ROUTE_EXCEPTIONS` in `banned_patterns.py`; `PRE_SESSION_PATHS` in `identity/routing.py`.

## Enforcement
- [x] Lint rule: ROUTE-001's list names the three paths.
- [x] Architecture / dependency rule in CI: the router refuses `PRE_SESSION` on any other path.
- [x] Test: route introspection checks that every pre-session route is on the exception list; integration tests cover MFA refusal, cookie flags, reuse and sign-out.
- [x] Hook or protected path: both lists are protected.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Never add a path to `PRE_SESSION_PATHS` without extending this ADR. The portal BFF gets its own paths through P-08's ADR.

**Do**
```
@auth_router.post("/refresh", action=PRE_SESSION, response_model=SessionTokenOut)
```

**Don't**
```
@router.get("/v1/anything", action=PRE_SESSION, ...)  # the router refuses it
```

## Revisit when
The portal BFF lands (P-08-T10), or G-02 records IdP-enforced MFA for SSO firms.

## Related
- ADRs: extends ADR-152's exception list; implements ADR-141's staff BFF; sets ADR-030's limits.
- Plan: P-54, P-45, DEC-22, DEC-140; P-01-T09; P-01 Q1.
- Specs: SHL-06.
