---
id: ADR-064
title: Living AI threat model; all client-system strings are untrusted
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
Agents read content from clients and their systems and can act. Injection can arrive through uploads, emails, and ordinary ledger fields such as vendor names and journal memos.

## Decision
An AI threat model is maintained at `docs/architecture/ai-threat-model.md` and reviewed whenever an agent, tool or data source is added. Every string originating from a client or client system — uploads, emails, ledger fields, vendor and customer names, memos, descriptions — is treated as untrusted data by context builders.

## Options considered
### Living model, broad untrusted boundary — chosen
- Pros: Catches injection via overlooked channels
- Cons: More wrapping in context builders
- Chosen.

### Only uploads treated as untrusted
- Pros: Less work
- Cons: Ledger fields become an injection channel
- Rejected.

## Consequences
**Positive**
- Injection surface is understood and tracked

**Negative / costs accepted**
- Ongoing maintenance

**Follow-up work**
- Initial threat model document

## Enforcement
- Connector-sourced fields are typed as `Untrusted[str]`; context builders accept them only inside untrusted blocks
- PR checklist requires a threat-model update when adding agents, tools or sources

## Guidance for agents
Pass connector strings through as untrusted values.

**Do**
```python
inputs = {'memo': Untrusted(entry.memo)}
```

**Don't**
```python
prompt += f'Memo: {entry.memo}'
```

## Revisit when
Never expected to change.

## Related
- ADR-052
- ADR-065
