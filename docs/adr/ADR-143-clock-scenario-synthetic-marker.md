---
id: ADR-143
title: Business clock, scenario loader and the firm-level synthetic marker
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
The backend has 51 direct `now()` call sites, so no demo date, golden-date test or seed epoch can be reproduced. SPEC-001 AC-14 marks demo data by suffixing every client and entity name with " (Synthetic)", which breaks canonical names on the design screens. Plan decision DEC-27 settles this; this ADR is P-37 in the plan's ADR backlog.

## Decision
- **Clock.** Business time comes from `abacus.kernel.clock`, which replaces the 51 direct `now()` calls. The demo clock defaults to Mon 14 Sep 2026, 9:24 AM CT. It can be set only on synthetic tenants and is refused in production.
- **Scenario loader.** `scenarios/brightwater_hale` replays a dated event timeline (epochs E0, E1, E2) through the service APIs, on local and staging only.
- **Synthetic marker.** The firm carries `firms.synthetic = true`. Names carry no suffix.
- **Fixtures.** A TypeScript seed now, the Python scenario later, served in the existing fetch-swap fixture mode (no MSW).

## Options considered
### Option A: a clock abstraction plus a firm flag — chosen
- Pros: reproducible dates; canonical names on every screen; seeds exercise real audit and outbox paths.
- Cons: touches red-zone call sites; one reversible migration for database business time.

### Option B: keep `now()` and the "(Synthetic)" suffix
- Pros: no work.
- Cons: the demo date cannot be pinned; names differ from the design.
- Why rejected: golden-date tests and the Brightwater Hale timeline need one injectable clock.

## Consequences
**Positive**
- Golden-date tests and seed epochs are deterministic.
- Seeds go through service APIs, so audit events and outbox rows are real.

**Negative / costs accepted**
- Every business-path module must adopt the clock; red-zone adoption needs independent tests.
- Two seed paths (TypeScript now, Python later) until the scenario package replaces the first.

**Follow-up work created**
- Code: `backend/src/abacus/kernel/clock.py`, tenant demo-clock setting and `abacus_now()` (epic F-04, S1-S2; tasks F-04-T02, T06, T07); adoption in red and amber modules (F-04-T11, T16, S3); scenario loader (F-04-T13, S3).
- Specs: SPEC-001 AC-14 is amended (see Related); a scenario spec for the timeline and epochs (F-04-T01, S1).
- Glossary: none.
- Matrix: `demo_clock.set` action, allowed only for synthetic tenants outside production (F-04-T07, S2).
- Registry: none new; `firms.synthetic` is a column, and the canonical-name lint replaces suffix checks (F-04-T09).

## Enforcement
- [x] Test: independent tests for production refusal and the database synthetic check (F-04-T08).
- [x] Test: canonical-name and seed-contamination lint (F-04-T09).
- [x] Lint rule: business-path code calls `kernel.clock`, not `now()` (adopted in F-04-T11, T16).
- [ ] Advisory only: none.

## Guidance for agents
Read time from `kernel.clock`. Mark a demo firm with `firms.synthetic`, never with a name suffix. Load demo data through the scenario loader, which calls service APIs.

**Do**
```python
from abacus.kernel import clock
created_at = clock.now()
```

**Don't**
```python
created_at = datetime.now(timezone.utc)   # direct call
name = f"{name} (Synthetic)"              # suffix marker
```

## Revisit when
The Python scenario package fully replaces the TypeScript seed, or the first real firm goes live.

## Related
- Plan: P-37 (`docs/plan/09-decisions-adrs.md` section 9.4.2); DEC-27 (decided); G-E01, G-E02; FE-11, D-FE-7.
- Amends SPEC-001 AC-14: its clause "every client name and client entity name ends in ' (Synthetic)'" is replaced by the firm flag `firms.synthetic = true`. The rest of AC-14 (built-in word lists, no real-world identifier) stands.
- Consistent with ADR-085: real client data still never enters the repository; only the marker moves from names to the firm.
- ADRs: ADR-135 (one reversible migration for database business time).
