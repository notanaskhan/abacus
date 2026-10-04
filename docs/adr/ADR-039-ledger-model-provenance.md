---
id: ADR-039
title: Common ledger model with source identifiers and authorship
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
Ledgers differ in structure. Evidence and future procedures need a single model, and journal entry testing will need data on who posted what and when.

## Decision
All ledgers map into one model: accounts, trial balance lines, journal entries and lines, typed transactions, customers, vendors, aging buckets, bank transactions and attachment references. Every record carries its source system identifier. Journal entries also carry creator, last modifier, created and modified timestamps where the provider exposes them.

## Options considered
### Rich common model now — chosen
- Pros: Enables future procedures without re-pulling
- Cons: Slightly more mapping work
- Chosen.

### Minimal model for MVP
- Pros: Faster
- Cons: Re-pull every client later
- Rejected.

## Consequences
**Positive**
- Journal entry testing becomes possible without new extraction

**Negative / costs accepted**
- Mapping effort per provider

## Enforcement
- Schema: `source_id` and `source_system` NOT NULL on ledger tables
- Golden normalisation tests assert authorship fields are mapped where available

## Guidance for agents
Map source identifiers and authorship.

**Do**
```python
JournalEntry(source_id=raw['Id'], created_by=raw.get('CreatedBy'), source_created_at=...)
```

**Don't**
```python
JournalEntry(amount=..., date=...)  # provenance dropped
```

## Revisit when
A provider exposes richer metadata worth capturing.

## Related
- ADR-038
