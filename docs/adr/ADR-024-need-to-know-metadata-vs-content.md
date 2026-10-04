---
id: ADR-024
title: Need to know: admins see engagement metadata, not content
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Firm admins are often not auditors, and admin accounts are the most valuable phishing target. Firms are expected to restrict client information to people who need it, but admins still need operational visibility.

## Decision
Firm admins can see the metadata of every engagement they are not walled from — name, status, team, milestones and progress — but not evidence, client financial data, request item contents or messages. To see content, an admin joins the engagement; self-joining is allowed, notifies the engagement team, and is audited. Practice leaders and quality partners have read access to content in their scope, subject to walls. Ethical walls always apply.

## Options considered
### Metadata yes, content no — chosen
- Pros: Operational visibility without reading financials; small breach radius
- Cons: More nuanced to build
- Chosen.

### Strict: settings and users only
- Pros: Strongest
- Cons: Too much friction for small firms
- Rejected.

### Admins see everything
- Pros: No friction
- Cons: Largest breach exposure; weak compliance story
- Rejected.

### Firm-configurable
- Pros: Flexible
- Cons: Settings drift to the convenient option
- Rejected.

## Consequences
**Positive**
- A compromised admin account exposes no client financial data
- Admin access to content is deliberate, visible and recorded

**Negative / costs accepted**
- Admins must join engagements to view content

**Follow-up work**
- Engagement-team notification on admin self-join

## Enforcement
- Separate actions: `engagement.read_metadata` versus `engagement.read` and content actions
- Permission matrix grants firm_admin only metadata actions without membership
- Test: admin without membership receives metadata fields only; content endpoints deny

## Guidance for agents
Serve metadata and content through separate endpoints and actions.

**Do**
```python
await authorise(ctx, 'engagement.read_metadata', eng)  # dashboard view
```

**Don't**
```python
return EngagementWithEvidence.from_orm(eng)  # admin dashboard leaking content
```

## Revisit when
Customers consistently require broader admin visibility, with evidence it's needed.

## Related
- ADR-023
- ADR-026
- ADR-027
