---
id: ADR-037
title: One connector contract with capability declarations
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
The platform will integrate many systems: ledgers, payroll, AP tools, banks and document stores. Each client's systems differ, so what can be retrieved differs per client.

## Decision
Every connector implements one interface: `capabilities()`, `authorise_url()`, `exchange_code()`, `refresh()`, `pull(dataset, period, cursor)`, `changes_since(ts)`, `fetch_attachment(ref)`, `health()`. Retrievability tiers are classified per client from the capabilities of that client's active connections, never hard-coded per request item.

## Options considered
### Single contract with capabilities — chosen
- Pros: New connectors slot in without touching the rest of the system
- Cons: Contract must stay general
- Chosen.

### Bespoke integration per provider
- Pros: Maximum flexibility
- Cons: Every connector becomes a special case
- Rejected.

## Consequences
**Positive**
- Adding a connector is contained work
- Classification adapts to each client automatically

**Negative / costs accepted**
- Some providers need adapters to fit the contract

**Follow-up work**
- Connector reference doc per provider

## Enforcement
- Abstract base class with a conformance test suite every connector must pass
- Classification code reads capabilities; a test fails if it references a provider by name

## Guidance for agents
Implement the contract and declare capabilities.

**Do**
```python
class QboConnector(Connector):
    def capabilities(self) -> set[Capability]:
        return {Capability.TRIAL_BALANCE, Capability.GL_DETAIL, Capability.ATTACHMENTS}
```

**Don't**
```python
if connection.provider == 'quickbooks':
    tier = 'A'
```

## Revisit when
The contract cannot express a new class of system without distortion.

## Related
- ADR-038
- ADR-045
