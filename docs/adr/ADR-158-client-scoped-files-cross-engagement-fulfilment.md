---
id: ADR-158
title: Client-scoped files and cross-engagement fulfilment
status: proposed
date: 2026-10-22
deciders: ayushkbhatia, notanaskhan
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Evidence belongs to an engagement today (`evidence_items.engagement_id NOT NULL`). Accrued's screens need files that belong to the client, not to one year's engagement: a permanent file of formation documents, an operating agreement, a plan document (FIL-01, CLI-01, SHL-21, ATT-08). Firms also fulfil one engagement's request from a file another engagement of the same client already holds (a 401(k) plan audit reusing the sponsor's payroll register). Plan decision DEC-33 settles it with option (b), declared scope kinds, over a "permanent file" pseudo-engagement. This ADR is P-40 in the plan's ADR backlog; ADR-145 (P-06, generalised `visible()`) already provides the `client` scope kind it reads through.

## Decision
- **Client-scoped evidence.** `evidence_items.client_id` is NOT NULL for every item (backfilled from the engagement). `engagement_id` and `work_item_id` become nullable, with `scope ∈ {engagement, client}` and `CHECK ((scope = 'client') = (engagement_id IS NULL))`. A client-scoped item has a client and no engagement.
- **Who reads it.** A person may read a client-scoped item's content when they may read content on at least one non-walled engagement of that client (ADR-145's `client` scope kind; walls on `client_id` answer 404, DEC-43). Metadata-only reads follow the same rule with the metadata action.
- **Cross-engagement fulfilment.** A request item may be fulfilled by evidence from another engagement of the same client, or by a client-scoped item of that client. Fulfilment foreign keys relax from "same engagement" to a database trigger that refuses any fulfilment whose evidence belongs to a different client. Reuse is a reference to the existing version, never a copy (ADR-004 immutability holds; one version, many fulfilments).
- **Writes.** Client-scoped uploads run through the same scan, preview and screening pipeline as engagement uploads. The migration (`evidence_scope`) lands with N-01 (S13); F-03-T38 records the decision only.

## Options considered
### Option A: declared scope kinds (client-scoped evidence plus a same-client trigger) — chosen
- Pros: one evidence model; walls and `visible()` already speak `client_id`; reuse without copies keeps one immutable version.
- Cons: a nullable `engagement_id` touches every evidence query; the trigger is red-zone code.

### Option B: a "permanent file" pseudo-engagement per client
- Pros: no schema change to evidence.
- Cons: a fake engagement shows up in lists, counts, gates, independence and billing; every rule needs an exception for it.
- Why rejected: it leaks into every engagement rule and every count (DF-33).

### Option C: copy files into each engagement that needs them
- Pros: no cross-engagement reads.
- Cons: two versions of one document; retention and legal holds diverge; storage doubles.
- Why rejected: breaks ADR-004's one-version rule and P-14's holds.

## Consequences
**Positive**
- FIL-01, SHL-21 and ATT-08 have one place for client-level documents, and reuse is traceable.

**Negative / costs accepted**
- Every evidence list query and LIST-001 check gains the `client` scope kind.
- The same-client trigger must stay in step with fulfilment rules.

**Follow-up work created**
- Code: the `evidence_scope` migration and the trigger (N-01, S13); `visible()` client kind for evidence reads (ADR-145 machinery); FIL-01 routes.
- Tests: generated "visible agrees with authorise" cases for client-scoped evidence; a cross-client fulfilment refused by the trigger.

## Enforcement
- [ ] Test: a cross-client fulfilment is refused by the database (N-01).
- [ ] Test: a walled person gets 404 for a client-scoped item of that client (INV-3).
- [ ] Lint rule: LIST-001 covers the `client` scope kind (ADR-145).
- [ ] Advisory only — none.

## Guidance for agents
Read evidence through `visible()` with its scope kind; never assume `engagement_id` is set. Reuse a file by referencing its version, never by copying it. Until N-01's migration lands, evidence stays engagement-scoped.

## Related
- Plan: P-40 (section 9.4.2); DEC-33; chapter 03 §3.1.4 step 6; F-03-T38.
- ADRs: ADR-004 (immutable evidence), ADR-026 (walls), ADR-145 (scope kinds), ADR-146 (portal scopes).
