---
id: ADR-088
title: Build once, promote; health-checked rollouts
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
Rebuilding per environment ships untested artefacts; manual deploys and slow rollbacks cause outages.

## Decision
Each container image is built once in CI and promoted unchanged from staging to production. Main deploys to staging automatically; production deploys require founder approval. Rollouts are health-checked and roll back automatically on failing checks or alarms. Frontend and API tolerate version skew; the API remains backward compatible within its version.

## Options considered
### Promote one artefact — chosen
- Pros: What was tested is what ships
- Cons: Registry and promotion pipeline
- Chosen.

## Consequences
**Positive**
- Predictable deploys with fast rollback

**Negative / costs accepted**
- Pipeline setup

## Enforcement
- Deploys reference image digests, never tags
- Rollback tested in staging regularly

## Guidance for agents
Deploy by digest.

**Do**
```yaml
image: registry/api@sha256:<digest>
```

**Don't**
```yaml
image: registry/api:latest
```

## Revisit when
Never expected to change.

## Related
- ADR-083
- ADR-089
