---
id: ADR-108
title: Clients choose to connect or to export; connecting is never required
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
Connecting an accounting system is the fastest way to provide evidence, but some clients won't grant access, and a few systems have no live connector.

## Decision
- **The client's first screen offers two options side by side:** "Connect (fastest)" and "Export instead" (ADR-107's file import, with guided steps for their system).
- **Connecting is never required.** Every request can be met by export or upload.
- **Consent copy follows ADR-040:** read-only access, what is read, how to revoke it.

## Options considered
### Both options, side by side — chosen
- Pros: honest choice; no client is blocked
- Cons: two paths to support

### Connect first, export hidden behind "other options"
- Pros: more connections
- Cons: pressures clients; contradicts the consent posture of ADR-040
- Rejected.

## Related
ADR-040, ADR-107.
