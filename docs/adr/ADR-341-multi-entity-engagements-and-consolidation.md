---
id: ADR-341
title: "Multi-entity engagements and consolidation: engagement entities, ledger-owned mapping and consolidation, the taxonomy as firm content"
status: proposed
date: 2026-10-29
deciders: ayushkbhatia, audit CPA
risk_zone: red
proposal: P-63
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by A-03-T24 (TASK-2301) in S18 as pre-window work for A-03 (S20–S23).
The plan names this ADR "ADR-154"; that is a P-ID alias, and ADR-154 is P-67 (observability
vendors) on `main`, so this ADR takes ADR-341 from the S18 block. Acceptance is due **Fri Jul 23,
2027 (S19)**, before A-03 T03, T06 and T08 build on it; each of those cites ADR-341. Extends
ADR-136 (P-04) and amends ADR-006's single-entity interface.

## Context
ADR-006 models client entities from day one: a client has entities, ledger data and connections
are entity-scoped, engagements reference one or more entities, and the MVP interface shows one.
A group audit (AU-C 600, SAS 149), a household tax engagement or a combined CAS close needs the
engagement to span several entities, each with its own trial balance, mapped to one taxonomy and
consolidated with eliminations.

DEC-65 decided that SAS 149 group audits are no-go until the Dec-2028 year-ends at plan velocity,
but that A-03 lands the single-entity mapping and the group data model on synthetic data so A-09
adds group work without a schema rebuild. DEC-66 decided that `ledger` owns account mappings and
consolidation structures and stays dependency-free (Q-15), and that the grouping and FS-line
catalogue is versioned firm content, not code.

Much is already on `main`: `engagement_entities` (migration 0068: role `primary`, `component` or
`household_member`, an ownership percentage, one primary per engagement, created by the
engagement trigger); entity-scoped connections with one live ledger per entity
(`connections_one_live_ledger`, migration 0195, ADR-045); the trial balance of record per
engagement, work item, entity, label and period (A-02, SPEC-309/311/333); and the first slice of
account mapping (SPEC-316, migration 0079: grouping sets with draft and published versions, one
mapping set per trial balance of record, rule mappings computed on read from number ranges, and
people's edits insert-only with the newest winning). This ADR ratifies that shape and fixes the
rules for what comes next.

## Decision
1. **An engagement's entities are `engagement_entities`.** Every engagement has exactly one
   `primary` row (`engagements.client_entity_id` stays, as the primary entity, expand-only). Group
   audits add `component` rows; household engagements add `household_member` rows. Adding a
   non-primary entity is gated by `ff.group_audit` (owned by A-09) until DEC-65's season; nothing
   in A-03 creates one.
2. **`ledger` owns account mappings and consolidation structures and stays dependency-free.** It
   has no routes, no subscribers and no imports of other modules; callers authorise and pass
   identifiers (DEC-66, Q-15). The HTTP routes, the `trial_balance.version_created` subscriber and
   the sign-off orchestration live in `assurance`, the precedent A-02 set with
   `assurance/routes_tb.py`.
3. **The taxonomy is firm content.** Grouping sets, their groupings (with a class), FS lines (with a
   normal balance) and number-range rules are versioned: imported into a draft with its problems,
   published once by a person (`published_actor_kind = 'human'`), frozen after publication. They
   never live in code, a migration or the seed (AGENTS.md rule 16; SQMS 1). A mapping set pins the
   published version it was created on; pinning a grouping set to an engagement template version
   arrives with K-03 (P-41).
4. **One mapping set per entity's trial balance of record** (`UNIQUE (tenant_id, trial_balance_id)`,
   as built). The trial balance of record already carries the entity, so A-09's multi-entity
   mapping is one set per entity's trial balance with no schema change.
5. **Mappings are computed, edits are recorded.** Rule mappings (prior-year code first, then number
   ranges) are computed on read, so a new trial balance version maps without writing anything;
   people's edits stay insert-only with the newest per account winning (as built, SPEC-316). The
   plan's stored `account_mappings` and `account_mapping_events` tables (A-03 §4.2 M-B) are
   replaced by this design; anything A-03 still needs (the prior-year source, run state,
   confirmation as an L1 sign-off through `review.api`, staleness against a `content_hash`) is added
   expand-only beside it. Display status (In progress, Prepared, Reviewed, Changed after sign-off)
   is computed, never stored. No model maps an account in A-03; the TB mapper's suggestions are
   A-09's, as proposals a person adopts (ADR-005).
6. **Consolidation is code in `ledger`.** A consolidated view sums the mapped trial balances of an
   engagement's entities by FS line, with ownership from `engagement_entities`, computed and
   golden-tested (ADR-050). Eliminations are adjustments of kind `elimination` in the
   `adjustments` module's proposed entries (C8), posted to a consolidated layer and decided by a
   person, never a separate write path into ledger snapshots, which stay immutable (ADR-004).
   Foreign-currency translation is out of scope: ledger refuses non-USD today, and a currency
   decision needs its own ADR.
7. **Connections stay entity-scoped.** One live ledger connection per entity holds until A-09,
   which relaxes `connections_one_live_ledger` so one multi-subsidiary connection (NetSuite
   OneWorld) can serve N subsidiary entities, each pull landing in its own entity's trial balance
   of record. Connectors stay read-only (ADR-040).
8. **The fallback is always available:** upload-only trial balances per entity plus manual
   eliminations (DEC-65).

## Options considered
### Option A: engagement entities, ledger-owned mapping and consolidation, taxonomy as content — chosen
- Pros: built on what exists; A-09 is additive; mapping is reproducible from rules and edits;
  content stays out of commits.
- Cons: routes and subscribers live in `assurance`, one step away from the data they serve.

### Option B: the taxonomy in methodology or a `reporting` module
- Pros: closer to templates and statements.
- Cons: a second owner for mapping; consolidation split across modules; cycles risk.
- Why rejected: DEC-66.

### Option C: a group engagement as a parent of per-entity engagements
- Pros: each entity keeps today's single-entity screens.
- Cons: team, walls, independence, sign-offs and requests split across engagements; consolidation
  crosses engagement boundaries.
- Why rejected: ADR-006 already lets one engagement reference several entities.

### Option D: store every account mapping row (A-03 §4.2 M-B as written)
- Pros: one row per account to read.
- Cons: a new trial balance version rewrites rows; duplicates what 0079 computes on read.
- Why rejected: the built compute-on-read design re-maps a new version without writes; only the
  missing state is added.

## Consequences
**Positive**
- A-09 group audits and household engagements add rows and flags, not schema rebuilds.
- Firm taxonomy edits cost no deployment; every mapping is explained by a rule or a named person.

**Negative / costs accepted**
- `assurance` hosts ledger's HTTP surface.
- Currency translation and the multi-subsidiary connection wait for their own work (A-09).

## Compliance
- Tests: a test that `ledger` imports no other module (import-linter); a test that no A-03 service
  writes a non-primary `engagement_entities` row; publication refused to non-humans; edits
  insert-only; consolidation and elimination goldens with A-09.
- Data classification: account names and amounts `confidential` (ADR-031).

## References
- DEC-65, DEC-66 (`docs/product/decision-log.md`); P-63 (`docs/plan/09-decisions-adrs.md` §9.4.2).
- `docs/plan/epics/A-03.md` §0.1, §4.1, §4.2 M-B, §7, §11 (R5, R6, R10, QA-7, QA-8).
- ADR-004, ADR-005, ADR-006, ADR-040, ADR-045, ADR-050, ADR-136; SPEC-316, SPEC-540.
