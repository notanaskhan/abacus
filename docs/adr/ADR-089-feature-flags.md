---
id: ADR-089
title: Release decoupled from deploy through feature flags
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
Shipping code and exposing behaviour at the same moment makes every deploy a release risk. Flag sprawl creates hidden complexity.

## Decision
New behaviour ships behind feature flags and is enabled per firm. Model and prompt rollouts use the same mechanism. Every flag has an owner and an expiry date; expired flags fail a CI check until removed.

## Options considered
### Per-firm flags with expiry — chosen
- Pros: Safe staged releases; controlled sprawl
- Cons: Flag hygiene work
- Chosen.

## Consequences
**Positive**
- Staged rollouts and instant switch-off

**Negative / costs accepted**
- Flag maintenance

## Enforcement
- Flag registry file with owner and expiry; CI fails on expired flags

## Guidance for agents
Register flags with an owner and expiry.

**Do**
```yaml
support_finder_v2: {owner: founder, expires: 2027-03-31}
```

**Don't**
```yaml
if os.getenv('NEW_THING'): ...
```

## Revisit when
Never expected to change.

## Related
- ADR-074
- ADR-088
