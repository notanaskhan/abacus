---
id: ADR-090
title: Workflow-safe deployments
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
Engagement agents run for months. Changing workflow logic without versioning breaks every running engagement at once.

## Decision
Any change to workflow logic uses Temporal's versioning so running workflows continue on their original path. Replay tests against recorded histories gate every deploy.

## Options considered
### Mandatory versioning — chosen
- Pros: Running engagements are never broken by a deploy
- Cons: Versioning discipline
- Chosen.

## Consequences
**Positive**
- Safe continuous deployment with long-running agents

**Negative / costs accepted**
- Old code paths retained until workflows complete

## Enforcement
- Replay test is a required check
- Reviewer checklist flags workflow changes lacking a version marker

## Guidance for agents
Branch on versions for workflow changes.

**Do**
```python
if workflow.patched('reminder-cadence-v2'):
    await new_cadence()
else:
    await old_cadence()
```

**Don't**
```python
# editing the reminder loop in place in a running workflow
```

## Revisit when
Never expected to change.

## Related
- ADR-017
- ADR-062
