---
id: ADR-111
title: Client-facing pre-checks are mechanical, with fixed wording
status: accepted
date: 2026-10-11
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Telling a client at upload time that a file covers the wrong period saves a round trip. Model-written text sent to clients is a different risk.

## Decision
- **Pre-checks shown to clients are mechanical only:** wrong period, wrong entity, stale as-of date, unreadable, duplicate, totals that don't add up. Each message comes from a deterministic template.
- **No model-generated text reaches a client** until both the firm's autonomy policy and the data boundary (ADR-112) allow it. A person approving a model draft does not lift this; until the boundary lifts, model drafts for clients exist only on synthetic data.
- Judgement-based flags (wrong kind of document, looks altered) stay on the firm's side.

## Options considered
### Mechanical only, fixed wording — chosen
- Pros: predictable, testable, no model text to clients
- Cons: fewer problems caught before submission

## Related
ADR-005, ADR-050, ADR-061, ADR-065, ADR-110, ADR-112.
