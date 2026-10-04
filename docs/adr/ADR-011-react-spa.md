---
id: ADR-011
title: React single-page app built with Vite
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
The app is entirely behind authentication; it needs no SEO or server rendering. A second server runtime would create another place for business logic and authorisation to leak.

## Decision
The frontend is a React SPA built with Vite and TypeScript, using TanStack Router, TanStack Query, Tailwind and shadcn/ui as the base of `packages/ui`. Firm and client users share the app through separate route trees. All authorisation is enforced by the backend. The frontend contains no business logic and calls the backend only through the generated API client.

## Options considered
### Vite SPA — chosen
- Pros: Simple; static hosting; no second backend
- Cons: No server rendering
- Chosen.

### Next.js
- Pros: Popular; strong tooling
- Cons: Second backend; server/client component pitfalls; hosting complexity
- Rejected for this app; acceptable for a separate marketing site.

## Consequences
**Positive**
- A single place for business logic: the backend
- Static hosting on CloudFront

**Negative / costs accepted**
- No server rendering

## Enforcement
- ESLint rule bans `fetch` and HTTP libraries outside `packages/api-client`
- Design system components only, enforced by reviewer checklist and lint rule against raw styled primitives where a component exists

## Guidance for agents
Use the generated client and design-system components.

**Do**
```ts
const { data } = useQuery(api.requests.list.queryOptions({ engagementId }))
```

**Don't**
```ts
const res = await fetch(`/api/requests?engagement=${id}`)
```

## Revisit when
A public, SEO-dependent surface is needed inside the app.

## Related
- ADR-012
- ADR-013
