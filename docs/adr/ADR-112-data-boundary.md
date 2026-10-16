---
id: ADR-112
title: AI runs only on synthetic tenants, enforced in the AI gateway
status: superseded by ADR-115
date: 2026-10-11
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-031 requires zero-retention and no-training terms before client data reaches a model provider. SPEC-026 (TASK-049) built the enforcement; this records it as a decision.

## Decision
- **Settings:** the only allowed data boundary is `synthetic_only`. Real routes are refused in staging, production and tests, and allowed in `evaluation`, or locally behind an explicit flag.
- **Per call:** before any network call on a real route, the AI gateway requires the call's firm to be marked synthetic (`firms.synthetic`, set only by seeding and evaluation runs, never by the application). Unregistered or not synthetic means refused, audited and counted.
- **Lifting the boundary** needs recorded provider terms (an ADR), staging, and a spec that starts in shadow mode with passing evaluations on the client-data route (ADR-113).

## Related
ADR-019, ADR-031, ADR-111, ADR-113; SPEC-026.
