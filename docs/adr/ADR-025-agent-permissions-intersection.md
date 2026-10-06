---
id: ADR-025
title: Agent permissions are an intersection, enforced in tools
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
Agents process untrusted client content that may contain prompt injection. If the model can influence permissions, one malicious document could expose other data.

## Decision
An agent's effective permissions are the intersection of the agent role's permissions, the initiating human or system actor's permissions, and the task's declared scope. Authorisation is enforced inside every tool using the agent's context; the model never decides permissions. Agent contexts never hold decision actions (ADR-005). The delegation chain is recorded on every agent action.

**Amended 2026-10-06 (TASK-011, founder decision).** An action no human role holds (agent and system only, such as `screening.run`) can't be intersected with the initiator's right to that action. For such an action the initiator must instead be allowed `evidence.read` on the same engagement, so the agent stays within the initiator's reach (founder decision 2026-10-06, TASK-011).

## Options considered
### Intersection, enforced in tools — chosen
- Pros: Prompt injection cannot escalate privileges
- Cons: Tools must all check
- Chosen.

### Agent role permissions only
- Pros: Simpler
- Cons: Agents could exceed their initiator
- Rejected.

### Model instructed to respect permissions
- Pros: None
- Cons: Trivially bypassed
- Rejected.

## Consequences
**Positive**
- A successful injection can only misbehave within permissions already held

**Negative / costs accepted**
- Every tool must call `authorise`

## Enforcement
- Tool registry wraps every tool with an `authorise` call; unregistered tools cannot be invoked
- Test: a tool called with a context lacking scope is denied regardless of model output
- Agent context type has no path to decision actions (type-level and runtime checks)

## Guidance for agents
Tools authorise with the agent context they receive.

**Do**
```python
@tool(action='evidence.read')
async def get_evidence(ctx: AgentCtx, version_id: UUID) -> EvidenceView: ...
```

**Don't**
```python
async def get_evidence(version_id: str):  # no context, no authorisation
    return repo.get(version_id)
```

## Revisit when
Never expected to change.

## Related
- ADR-005
- ADR-019
- ADR-023
