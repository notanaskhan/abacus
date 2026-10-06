---
id: ADR-102
title: "visible() takes the read action and the engagement column"
status: proposed
date: 2026-10-06
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-027 sketches `visible(ctx, resource_type)` for list queries. Building it in TASK-007 showed two things the sketch leaves out:
- Which rows are visible depends on the action. A firm admin sees every engagement's metadata (`engagement.read_metadata`) but no engagement's content (`engagement.read`, ADR-024).
- Engagement-scoped tables name the engagement column differently: it is `id` on `engagements` and `engagement_id` on everything else.

## Decision
`visible(ctx, action, engagement_id_column)` returns a SQLAlchemy filter for the rows whose engagement the actor may perform `action` on. The action must be a read action, and one without `mfa_recent`, `requires` or `notify` conditions; `visible` raises otherwise. Every list route passes the action it declared. This refines ADR-027's signature; everything else in ADR-027 stands.

## Options considered
### Action and column — chosen
- Pros: Matches the matrix exactly (decisions are per action). Works for any engagement-scoped table without per-model registration.
- Cons: The caller names the column, so passing the wrong column is possible. Mitigated by the repository list-method test ADR-027 already requires (TASK-008).
### `visible(ctx, resource_type)` with a registry
- Pros: Matches the original sketch.
- Cons: Still needs the action, and each model has to register its engagement column.
- Rejected.

## Consequences
**Positive**
- Admin metadata versus content is enforced in list queries, not only in `authorise`.

**Negative / costs accepted**
- One more argument at every list call.

**Follow-up work**
- TASK-008: a test that inspects every repository list method and fails if `visible()` is not applied (ADR-027 enforcement).

## Enforcement
- `visible` raises for non-read actions and for actions with conditions it can't apply.
- Route guard: building a `visible` filter counts as the route's check (`AbacusRoute`).

## Guidance for agents
**Do**
```python
q = select(Engagement).where(visible(ctx, "engagement.read_metadata", Engagement.id))
```
**Don't**
```python
q = select(Engagement)  # no visible(): every engagement in the tenant
```

## Revisit when
Lists span resources that aren't engagement-scoped (firm-level lists, client portal).

## Related
- ADR-024
- ADR-027
