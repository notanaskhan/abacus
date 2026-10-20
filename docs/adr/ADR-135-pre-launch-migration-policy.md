---
id: ADR-135
title: Until the first real firm is live, a breaking change is one reversible migration
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-091 requires expand-then-contract across several deploys, with throttled backfills. That protects live data. Today only synthetic data exists, so the discipline costs weeks of dual-write work for no protection. The plan needs three rewrites in a single step each: the engagement and work-item split (ADR-136), the request-status enum (DEC-09) and the `audit` -> `fs_audit` type value. Linear migration numbering also collides when two branches claim the same number.

## Decision
1. **Until the first non-synthetic firm is live in production**, a destructive or renaming change lands as **one reversible migration** (upgrade and downgrade both tested). The same change updates seeds, the scenario loader and generated clients. No alias or dual-write period.
2. **CI checks for a single Alembic head.** A branch that finds another head renumbers on rebase. The number is the next free one on `main`; put `[mig NNNN]` in the PR title.
3. **From the first non-synthetic firm onward**, ADR-091 applies in full: expand, backfill, switch, contract.
4. Everything else in ADR-091 stands in both periods: migrations run as a separate pre-deploy step and never at startup, and migration sessions set lock and statement timeouts. ADR-092 (busy-season changes) is unchanged.

## Options considered
### Option A: single reversible migrations until the first real firm — chosen
- Pros: work items, the request enum and the type rewrite each land in one step; no compatibility code to delete.
- Cons: the habit must flip at go-live; a mistake in a rewrite has no live-data safety net.

### Option B: strict expand/contract now (ADR-091 as written)
- Pros: one rule at all times.
- Cons: weeks of dual-write work against synthetic data only.
- Why rejected: no data to protect.

## Consequences
**Positive**
- The schema reaches its target shape before any real data exists.

**Negative / costs accepted**
- A rewrite mistake has no live-data safety net, so each migration is tested up and down on the seeded database.

**Follow-up work created**
- **Code:** single-head check in the quality gate and the `[mig NNNN]` convention. Epic F-03 (domain model migrations), S0 (numbering protocol S0-11, 22 Oct).
- **Code:** the work-item, lifecycle and request-status migrations as one step each, from 0066 (heads are at 0065). Epic F-03, S1-S4.
- **Specs, glossary, matrix, registry:** none.

## Enforcement
- [ ] CI: exactly one Alembic head.
- [ ] Test: each migration upgrades and downgrades on the seeded database.
- [ ] Advisory only for the go-live switch: it is a human decision, checked when the first firm is onboarded.
- [ ] Reviewer agent checklist item: seeds, scenario loader and generated clients updated in the same change.

## Guidance for agents
Before go-live, fold a breaking schema change into one migration and fix every caller in the same change. Never put a backfill in a migration that touches real data.

**Do**
```
0067_request_status_v2: rewrite statuses in place, swap the CHECK, update seeds (downgrade provided)
```

**Don't**
```
add a temporary alias column and a later "contract" migration for synthetic-only data
```

## Revisit when
The first non-synthetic firm goes live (strict ADR-091 starts), or real data is loaded into any shared environment earlier.

## Related
- P-ID: P-38 (docs/plan/09-decisions-adrs.md section 9.4); DEC-06.
- Amends: ADR-091 Decision sentence "Destructive changes use expand-then-contract across multiple deploys", for timing only. It applies only after go-live. All other ADR-091 clauses stand.
- Related ADRs: ADR-092, ADR-136.
- Docs: docs/plan/03-backend-architecture.md section 13.2.
