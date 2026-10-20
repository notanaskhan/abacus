---
id: ADR-152
title: Unauthenticated operational routes - /healthz and portal branding on an explicit allowlist
status: proposed
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Accept by 2026-11-13.** `AbacusRouter` refuses any route without a matrix action. A load balancer needs `/healthz`, and a portal visitor needs branding before sign-in. Plan decision DEC-59 names `GET /v1/portal/branding` and `/healthz` as the only unauthenticated routes; this ADR is P-45, drafted under Q-01-T10 and built under Q-01-T16. Without it, these routes would bypass the router ad hoc.

## Decision
- **Two allowlisted unauthenticated routes**, outside `AbacusRouter`, on the ROUTE-001 exception list: `/healthz` and `GET /v1/portal/branding`.
- **The list is explicit and checked by ROUTE-001** (a protected banned pattern); any other route without an action still fails.
- **The portal host is only a branding hint.** `/v1` is proxied same-origin.
- **`/readyz`** is added under Q-01-T16 on the same list; later proposals (P-01, P-08) extend the list through their own ADRs.

## Options considered
### Option A: explicit allowlist on the ROUTE-001 exception list — chosen
- Pros: the exception is visible and testable.
- Cons: every new public route needs an ADR.

### Option B: give the routes a matrix action
- Pros: no exception.
- Cons: an action needs a principal, and these have none.
- Why rejected: not adopted by the plan.

## Consequences
**Positive**
- No hidden unauthenticated route.

**Negative / costs accepted**
- Branding responses must carry no client data.

**Follow-up work created**
- Code: `/healthz` and `/readyz` routes and middleware (Q-01-T16, S1); independent tests (Q-01-T24, S1).
- Specs: POR-*, ADM-10, POR-20, SHL-06 (EP-02, EP-07, EP-19).
- Glossary: public route (`docs/product/glossary.md`).
- Matrix: none; the allowlist is the exception.
- Registry: ROUTE-001 exception list in `docs/architecture/protected-paths.md` and the lint config.

## Enforcement
- [x] Lint rule: ROUTE-001 fails any unauthenticated route not on the list.
- [ ] Architecture / dependency rule in CI: none.
- [x] Test: only listed paths answer without a token.
- [x] Hook or protected path: the exception list is protected.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Do not add an unauthenticated route. Propose an ADR that extends the list.

**Do**
```
PUBLIC_ROUTES = ("/healthz", "/readyz", "/v1/portal/branding")
```

**Don't**
```
@app.get("/v1/anything")   # outside AbacusRouter
```

## Revisit when
A third unauthenticated route is proposed, or branding needs per-visitor data.

## Related
- ADRs: amends ADR-013's clause "Pydantic models are the single source of truth..." only by adding two routes outside `AbacusRouter`; operates the ROUTE-001 rule.
- Plan: P-45; DEC-59; Q-01-T10, Q-01-T16, Q-01-T24.
- Specs: none.
