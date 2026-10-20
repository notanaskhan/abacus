---
id: ADR-141
title: Authentication and sessions use WorkOS AuthKit, with a BFF session for the portal
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-029 left the identity vendor pending a commercial check, with Clerk as the alternative. ADR-030 allows staff passwords, makes client MFA optional, and says refresh tokens rotate, but the web app keeps its access token in `sessionStorage` with no refresh tokens. Sign-in screens (SHL-06, POR-01, ADM-06) cannot be built until these are settled. Plan decision DEC-22 settles this; this ADR is P-54 in the plan's ADR backlog.

## Decision
- **Vendor.** WorkOS AuthKit, committed commercially in Sprint 0. The vendor proves identity only; roles and permissions stay in the application's database (ADR-029).
- **Staff.** SSO, or a passwordless email code plus mandatory MFA (TOTP or passkey). The password option is dropped. Firm sign-in starts on hosted AuthKit pages; the in-product T15 sign-in comes later.
- **Portal.** In-product T15 sign-in through a backend-for-frontend (BFF) session over WorkOS APIs, because hosted pages cannot be white-labelled per custom domain.
- **Sessions.** Access token in memory; refresh token in an httpOnly cookie behind the BFF.
- **Lockout and invitations (DEC-35).** Invitations last 14 days and are single-use. A sign-in code expires in 10 minutes and allows 5 attempts; three failed codes lock the account for 15 minutes, released by waiting or by a firm admin. Trusted devices last 30 days. Lockout, unlock and trusted devices live in `identity`.
- **MFA scopes (DEC-34).** MFA is required for portal scopes that carry tax return information, signing or approving.

## Options considered
### Option A: hosted AuthKit now, in-product T15 on WorkOS APIs where branding needs it — chosen
- Pros: SSO and MFA from day one; portal can be firm-branded.
- Cons: a BFF to build and operate; vendor dependency.

### Option B: hosted WorkOS pages only
- Pros: least code.
- Cons: cannot be white-labelled per custom domain at reasonable cost.
- Why rejected: the portal must never show the product name.

### Option C: keep ADR-030's password option
- Pros: no change.
- Cons: weaker staff authentication; vendor still pending.
- Why rejected: passwordless plus mandatory MFA replaces it.

## Consequences
**Positive**
- Vendor decision closed; no tokens in web storage; reuse of a refresh cookie can revoke the session.

**Negative / costs accepted**
- A red-zone BFF and session store to build and test.

**Follow-up work created**
- Code: `identity/workos.py` adapter and staging identity (epic Q-01, S0-S5; Q-01-T17); staff session BFF `/v1/auth/*`, `auth_sessions`, cookie rotation with reuse detection (epic P-01, S2-S7; P-01-T09); portal identity (epic P-08, S4-S11).
- Specs: SHL-06, POR-01, ADM-06 sign-in copy (DF-24) (epics P-01, S2-S7; R-01, S7-S18).
- Glossary: none.
- Matrix: sensitive actions keep `mfa_recent: required` (G-01, S6-S13).
- Registry: `workos` approved in `docs/architecture/dependency-allowlist.yaml` (Q-01-T05, S0-S5).

## Enforcement
- [x] Test: a staff session without a verified second factor is refused (P-01-T09).
- [x] Test: a reused refresh cookie revokes the session; cookie flags asserted (P-01-T15).
- [x] Test: tokens minted by another WorkOS environment are rejected (Q-01-T17).
- [x] Hook or protected path: red zone; `workos` is on the dependency allowlist.
- [ ] Advisory only: none.

## Guidance for agents
Authenticate through the `identity` WorkOS port. Never store roles in tokens, a token in web storage, or add a password field. Put MFA requirements in the matrix, not in routes.

**Do**
```yaml
export.create: {mfa_recent: required}
```

**Don't**
```ts
sessionStorage.setItem("access_token", token);
```

## Revisit when
WorkOS terms or per-host redirect limits block portal custom domains, or an incident at the vendor needs a second provider.

## Related
- Plan: P-54 (`docs/plan/09-decisions-adrs.md` section 9.4.2); DEC-22, DEC-34, DEC-35; FE-15, D-FE-3.
- Amends ADR-029: its Decision clause "Authentication uses WorkOS, subject to a final check of pricing and multi-organisation membership; Clerk is the alternative" is now decided as WorkOS AuthKit. "The vendor proves identity only" stands.
- Amends ADR-030: "otherwise password or passkey with mandatory MFA" becomes SSO or passwordless code plus mandatory MFA (no password); "Client users use passwordless email links with optional MFA" gains required MFA for the DEC-34 scopes; "rotating refresh tokens" are held in an httpOnly cookie behind the BFF. Fresh-MFA sensitive actions, idle and absolute limits stand.
