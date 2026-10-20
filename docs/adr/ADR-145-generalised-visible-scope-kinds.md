---
id: ADR-145
title: Generalised visible() with declared scope kinds
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
ADR-102 binds `visible()` to an engagement column. Home, Clients, Inbox, Files, Signatures and the portal list resources that have no engagement column. Without a decision, each list invents its own visibility rule. Plan decision DEC-33 settles this; this ADR is P-06 in the plan's ADR backlog.

## Decision
- `visible(ctx, action, scope)` takes a declared **scope kind**: `engagement` (today's behaviour), `work_item` (via its engagement), `client`, `client_entity` and `portal_scope` (a grant match).
- `client` scope: the user can read content on at least one non-walled engagement of that client, or the action is metadata-only.
- Every kind evaluates ethical walls on `client_id` and answers 404.
- `identity.api.allowed_actions(ctx, resource, candidates)` evaluates the matrix without recording a check. It powers `allowed_actions` in record projections and `GET /v1/me/capabilities`. The route guard still records the route's own action.

## Options considered
### Option A: declared scope kinds — chosen
- Pros: one visibility entry point for every list; walls apply uniformly.
- Cons: `Resource` gains work-item, client and entity facts.

### Option B: a "permanent file" pseudo-engagement
- Pros: no signature change.
- Cons: invents engagements that are not real; walls and counts distort.
- Why rejected: plan DEC-33 chose declared scope kinds.

## Consequences
**Positive**
- Non-engagement lists get the same wall and permission guarantees as engagement lists.

**Negative / costs accepted**
- Red-zone change to identity; every repository list must declare its kind.

**Follow-up work created**
- Code: generalised `visible()` and `allowed_actions()` (epic F-03, S3; tasks F-03-T27, F-03-T30).
- Specs: list specs name their scope kind (epics from S2).
- Glossary: none.
- Matrix: no new action; `visible` still reads only read actions (F-03, S3).
- Registry: LIST-001 repository-list test extended to every kind, plus the generated "visible agrees with authorise" property test (F-03-T27).

## Enforcement
- [x] Test: LIST-001 requires a `visible()` predicate on every repository list, for all five kinds.
- [x] Test: generated property test "visible agrees with authorise".
- [x] Test: a walled user gets 404 through every scope kind (F-03-T27).
- [ ] Advisory only: none.

## Guidance for agents
Declare the scope kind a list uses and pass the read action the route declared. Client-level evidence rules belong to the separate P-40 ADR.

**Do**
```python
stmt = select(Doc).where(visible(ctx, "document.read", scope="client_entity"))
```

**Don't**
```python
stmt = select(Doc).where(Doc.engagement_id.in_(my_engagements))   # hand-rolled filter
```

## Revisit when
A new resource kind has no fitting scope kind, or P-40 changes client-level evidence reads.

## Related
- Plan: P-06 (section 9.4.2); DEC-33 (decided). P-40 (client-scoped evidence) is a separate ADR, not decided here.
- Amends ADR-102: its signature `visible(ctx, action, engagement_id_column)` becomes `visible(ctx, action, scope)`, where `engagement` is one scope kind. The clauses that the action must be a read action without `mfa_recent`, `requires` or `notify` conditions, and that every list route passes its declared action, stand. ADR-102's own refinement of ADR-027's signature is unchanged.
- ADRs: ADR-026 (walls, unchanged), ADR-139 (`allowed_actions` in projections).
