---
id: ADR-300
title: "Platform reference data split: frequently changing calendars are versioned, effective-dated database reference sets published by two people; engine parameters stay CPA-reviewed repo files"
status: accepted
date: 2026-10-29
deciders: ayushkbhatia, notanaskhan
risk_zone: amber
proposal: P-62
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** The plan reserved this as ADR-205 (P-62), to be drafted in S14 and accepted by
Fri May 28, 2027. It was never written to the repo, and ADR-205 is not free, so K-02-T01
(TASK-2100) writes it in the S16 reserved range and accepts it under DEC-76 (decided Nov 27,
2026) and the solo amendment (decide, record, carry on).

## Context
Chapter 03 (D-13) kept statutory parameters as versioned repo files; chapter 06 (D-OPS-20) put
platform reference data in the database, never in commits (X-8). Due dates, legal holidays,
disaster postponements, the Form 8879 form set and Pub 1345 tolerances, information-return
thresholds and retention minimums change during a season, sometimes within days (an IRS
postponement notice). A deploy per change costs a build, a cold cache and a freeze-window
exception (ADR P-29), and puts law-derived data behind one person's commit.

## Decision
Split, as DEC-76 decided:
1. **Database reference sets** (`platform`, global, no tenant) for data that changes often:
   `due_date_rules`, `legal_holidays`, `disaster_postponements`, `form_8879_set`,
   `information_return_thresholds`, `retention_minimums` and `standards_sets` (reserved:
   `state_breach_matrix`, `state_retention_rules`). Each set has immutable published versions with
   an `effective_from` date; consumers resolve the latest version effective on or before their
   `as_of` (ties to the highest version) and store the version id they used.
2. **Two-person publish.** A version is published only when its approver differs from its drafter
   (a database CHECK); every publication and withdrawal is an insert-only log row naming both. The
   operator CLI (K-02-T06) is the only writer until PLT-01 (G-04); it runs owner-only SECURITY
   DEFINER functions, never executable by `abacus_app`. The app reads published versions only
   through definer readers.
3. **Repo files reviewed yearly with a CPA** for engine parameters pinned by golden tests: MACRS
   and bonus, brackets, §199A, PTET rates, estate BEA, IRS plan limits, §6621 rates.
4. No rule content in a migration, a constant or the seed; staging and production sets are
   loaded with the CLI.

## Consequences
- A postponement or tolerance change is live minutes after the second founder approves it, with
  no deploy and no freeze exception.
- Every computed due date, clock or tolerance check names the reference-set version it used.
- Firms cannot edit platform sets; firm overrides (DF-10) are T-03's.
- K-02-T03 builds the tables and functions; K-02-T05 the service; K-02-T06 the CLI; K-02-T07 the
  calendar engine.
