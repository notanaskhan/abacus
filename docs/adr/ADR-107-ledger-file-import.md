---
id: ADR-107
title: A file-based ledger import is a connector with reduced capabilities
status: accepted
date: 2026-10-11
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-037 defines one connector interface; ADR-045 picks the first live connectors from discovery data. A live connector needs OAuth apps, partner approvals and per-client consent, so no real ledger reaches the platform until those exist. Clients can export a trial balance and general ledger detail from every system they use today.

## Decision
- **A file-based ledger import is a connector** under ADR-037, with reduced capabilities: `pull` from an uploaded export; no attachments; no change feed (`changes_since` is not supported); `health` reports the latest import. Its provenance method is `imported`.
- **The same pipeline as a live connector** (ADR-038, ADR-042): the raw export is stored write-once and fingerprinted, normalised, control totals must pass, a snapshot is taken, and rendering is deterministic.
- **Column mapping per export format is configuration**, applied as plain code at run time. It starts with QuickBooks Online and Xero, then NetSuite, Sage Intacct and QuickBooks Desktop, each with guided export instructions.
- **Retrievability tiers and request wording adapt to the connector's capabilities** (ADR-037), so an imported ledger never promises attachments or refreshes.
- **It is built before the first live connector.** This amends ADR-045's order, not its choice of live connectors.

## Options considered
### Import as a connector — chosen
- Pros: one pipeline, one provenance model, tiers already capability-driven
- Cons: each export format needs a mapping and tests

### A separate "upload a trial balance" path
- Pros: quick
- Cons: a second pipeline that skips control totals and snapshots
- Rejected.

## Consequences
Real ledgers arrive without OAuth or partner approvals. Imported data is as fresh as the last export; the request wording says so.

## Related
Amends ADR-037 (a connector may declare reduced capabilities) and ADR-045 (build order). ADR-038, ADR-042, ADR-108.
