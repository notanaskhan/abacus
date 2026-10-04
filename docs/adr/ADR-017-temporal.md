---
id: ADR-017
title: Temporal for durable workflows
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
Evidence requests stay open for weeks, wait on humans, react to events, and must survive crashes. Hand-rolled job state is where AI-built systems decay fastest.

## Decision
All asynchronous and long-running work uses Temporal (Temporal Cloud) with the Python SDK. Workflows contain only deterministic orchestration; all I/O happens in activities. Each module defines its workflows in `workflows.py`. Workflow changes use Temporal's versioning. All workflow payloads are encrypted with a payload codec before leaving our infrastructure.

## Options considered
### Temporal — chosen
- Pros: Battle-tested; built for long-running, human-in-the-loop work
- Cons: Learning curve; determinism rules
- Chosen.

### Inngest
- Pros: Simpler
- Cons: Less control and maturity at scale
- Rejected for the long term.

### Plain job queue
- Pros: Familiar
- Cons: Durability and waits must be hand-built
- Rejected.

## Consequences
**Positive**
- Durable, recoverable workflows with built-in waits for humans

**Negative / costs accepted**
- Determinism rules must be learned and enforced
- Temporal Cloud is an additional vendor

**Follow-up work**
- Temporal skill file for agents with the reference workflow pattern

## Enforcement
- Workflows run in the Python SDK's sandbox, which blocks many non-deterministic calls
- CI replays recorded workflow histories against new code to detect non-determinism
- Payload codec is mandatory; a test asserts payloads are encrypted
- import-linter forbids workflow modules from importing repositories or HTTP clients

## Guidance for agents
Orchestrate in workflows; do I/O in activities.

**Do**
```python
@workflow.defn
class PullLedger:
    @workflow.run
    async def run(self, a: PullArgs) -> None:
        await workflow.execute_activity(fetch_trial_balance, a, start_to_close_timeout=timedelta(minutes=5))
```

**Don't**
```python
@workflow.defn
class PullLedger:
    @workflow.run
    async def run(self, a: PullArgs) -> None:
        data = requests.get(url)  # I/O inside a workflow
```

## Revisit when
Operational cost or complexity of Temporal clearly outweighs its benefits at our scale.

## Related
- ADR-018
- ADR-021
