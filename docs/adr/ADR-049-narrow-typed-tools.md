---
id: ADR-049
title: Narrow, typed, intent-named tools
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
Generic tools let manipulated models compose harmful actions; verbose tool output wastes tokens on every step.

## Decision
Tools are named for intent with typed inputs and outputs, and authorise against the agent context (ADR-025). No generic query, HTTP or file-system tools. Results are compact, structured, paginated and carry IDs. Errors are actionable. Tool descriptions are versioned in the prompt registry and covered by evaluations.

## Options considered
### Narrow tools — chosen
- Pros: Injection-resistant; token-efficient
- Cons: More tools to write
- Chosen.

### Generic tools
- Pros: Few tools
- Cons: Exfiltration risk; unpredictable use
- Rejected.

## Consequences
**Positive**
- Prompt injection cannot compose harmful operations

**Negative / costs accepted**
- Tool count grows with capabilities

## Enforcement
- Tool registry rejects tools without typed schemas or an action
- Lint bans tools accepting raw SQL, URLs or file paths

## Guidance for agents
Define tools by intent.

**Do**
```python
@tool(action='ledger.search')
async def search_transactions(ctx, amount: Decimal, date_from: date, date_to: date, counterparty: str | None) -> TxnPage: ...
```

**Don't**
```python
@tool
async def run_sql(query: str) -> list[dict]: ...
```

## Revisit when
Never expected to change.

## Related
- ADR-025
- ADR-048
