---
id: ADR-340
title: "Sampling engine: a seeded, versioned, frozen in-product sampler; import kept as a path"
status: proposed
date: 2026-10-29
deciders: ayushkbhatia, audit CPA
risk_zone: red
proposal: P-57
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by A-03-T23 (TASK-2300) in S18 as pre-window work for A-03 (S20–S23).
The plan names this ADR "ADR-207"; that is a P-ID alias, not a reservation (`docs/adr/backlog.md`),
so it takes ADR-340 from the S18 block. Acceptance is due **Fri Jul 23, 2027 (S19)**, before A-03
T02, T04, T05, T07 and T10 build on it; each of those cites ADR-340.

## Context
AU-C 530 asks that a sample be re-performable: the population and proof of its completeness, the
sampling unit and deviation definition, the method and parameters with their source, the size,
any override and who approved it, and how items were selected. Build plan increment 10 assumed
samples are chosen outside the product and imported. The design (AUD-11 a–f) draws them in the
product: Marcus Delaney draws 25 Northwind participants with seed `0x5E2A91`; Simone Baptiste
draws 40 Granite Peak disbursements, 24 by threshold and 16 at random, with seed `0x7C31B4`.

DEC-81 decided (b), an in-product sampler, keeping import as a path (P-57). ADR-050 already keeps
models out of arithmetic, and ADR-132 already puts journal-entry selection in code with a recorded
seed (`sampling/selection.py`, `seeded_v1`, SPEC-037, TASK-083). What is still undecided, and what
this ADR settles, is how a population sample is drawn so that it re-performs years later on another
Python version, who may choose a seed, how sizes are set, and what is frozen.

## Decision
1. **In-product, by code.** Accrued draws population samples with a compute library under
   `backend/src/abacus/modules/sampling/compute/` (a protected path from A-03-T01). No model
   chooses, sizes, orders or projects a sample (ADR-050, INV-1). Import stays a path: a sample
   chosen outside Accrued is uploaded as evidence and linked to request items as today; it never
   reads as an Accrued draw and carries no seed.
2. **Only one stdlib RNG primitive.** Selection calls `random.Random(seed).getrandbits(32)` and
   nothing else from `random` (MT19937, whose output for a seed Python keeps stable). Rejection
   sampling to a uniform index, the partial Fisher–Yates walk and the ordering of results are
   Accrued code, so a change to `random.sample`, `shuffle`, `randrange` or `random()` cannot move
   an item. A unit test fails if any other `random` member is referenced under `sampling/compute/`.
   The population is ordered by its normalised record key before the walk; items keep their draw
   order as `position`.
3. **Versions are frozen.** Each algorithm is a registered entry in `SAMPLER_VERSIONS`, an opaque
   identifier that is never reused. Once registered, its function body does not change: a corpus
   test `(seed, population_hash, sampler_version) → items_hash` under
   `backend/tests/golden/sampling/corpus/` (protected) fails on any drift, and runs on both
   supported Python minors. New behaviour ships only as a new version. The first frozen version is
   registered as `2.3` so that the designed copy "Accrued sampler v2.3 · uniform without
   replacement" is true (A-03 QA-4). Methods in `2.3`: `attribute_nonstatistical` and
   `attribute_statistical` (uniform without replacement) and `threshold_random_stratified`
   (every item at or above the top threshold, a uniform draw inside each random stratum, none
   below the floor). Journal-entry selection's `seeded_v1` (ADR-132) is a separate, already
   frozen procedure and is unchanged.
4. **Golden fixtures are real output.** `0x5E2A91` gives the 25 designed Northwind participants in
   the designed order from census v2 (412 records); `0x7C31B4` gives strata 24 / 1,102 / 786 and
   40 items totalling 3,698,700 from Granite Peak's 1,912 disbursements. The synthetic census and
   GL fixtures are built by inverse construction so that the honest algorithm produces the designed
   lists; a fixture never overrides the algorithm's output (A-03 R2).
5. **The server draws the seed.** On a real firm the seed is a 24-bit value from `secrets`
   (`0 ≤ seed ≤ 16,777,215`, `seed_source = 'server'`). No API accepts a client-chosen seed; only the
   scenario loader on a synthetic tenant may pass `seed_source = 'scenario'` (403
   `seed_not_allowed` otherwise). Redrawing creates a new version and every earlier version stays
   visible, so seed shopping is always on the record (A-03 R13).
6. **Sizes are computed from firm content.** The size comes from the firm's published size table
   (a K-02 threshold-policy kind `attribute_sample_sizes`, read through `methodology.api`), never a
   constant in code, with a statistical cross-check computed in code (for zero expected deviations,
   the smallest n with (1 − tolerable rate)ⁿ ≤ 1 − confidence: 22 at 90% / 10% / 0%). The upper
   deviation limit is the exact binomial (Clopper–Pearson) bound; misstatement projection is a ratio
   estimate. Size and UDL tables are firm content; AICPA tables load only under a recorded licence
   (ADR-056).
7. **People decide.** A person starts each draw (the "Drawing" state is code, not the agent, DV-A1).
   A size below the computed size is an override that needs a rationale and is acknowledged by the
   approver. Approval is a level-2 `sign_offs` row through `review.api` (ADR-160), refused to the
   preparer (`not_preparer_of_target`), to agents, to system principals and to portal principals,
   with a DB CHECK `approved_actor_kind = 'human'`. Approval is refused while any completeness tie
   is off, and at least one tie is required before a draw.
8. **Several sample sets per work item**, each with immutable versions (DF-05's picker). Clients and
   third parties see only the item requests a sample produces, never its seed, parameters, size or
   population hash (INV-4).
9. **Later methods are later versions.** Monetary-unit sampling arrives as a new version with A-08
   (wave 6); HR and ticketing populations with X-01. Neither changes `2.3`.

## Options considered
### Option A: seeded, versioned, frozen in-product sampler; import kept — chosen
- Pros: re-performable from `(seed, population_hash, sampler_version)`; AU-C 530 record complete in
  one place; matches the design; golden-testable.
- Cons: Accrued owns an algorithm a CPA must review once per version; fixture construction work.

### Option B: import only (build plan increment 10)
- Pros: no algorithm to own.
- Cons: the design's draw, override and approval flow cannot exist; completeness and seed live
  outside the record.
- Why rejected: DEC-81.

### Option C: in-product sampler on `random.sample` or `numpy`
- Pros: less code.
- Cons: `random.sample` and `shuffle` have changed between Python versions; numpy is a new
  dependency with its own generator history; a re-performance could select different items.
- Why rejected: re-performability is the point.

## Consequences
**Positive**
- A reviewer, an inspector or a peer reviewer re-performs any draw from its record.
- Sizes, overrides and approvals are on the record with who decided.

**Negative / costs accepted**
- Every new method is a new version with its own corpus entry and CPA review.
- Fixture data must be inverse-constructed to make designed lists real output.
- The audit CPA reviews the `2.3` goldens before `sampling.sample_sets` flips for a pilot firm.

## Compliance
- Tests: corpus test per registered version on both Python minors; a unit test that only
  `getrandbits` is referenced under `sampling/compute/`; seed refusal on real tenants; approval
  refusals (preparer, agent, system, portal); override needs rationale and acknowledgement.
- Protected paths: `sampling/compute/` and `tests/golden/sampling/corpus/` (A-03-T01).
- Data classification: census display fields `confidential`; Restricted columns refused at the
  column map and never logged (ADR-031); seeds and parameters `internal`.

## References
- DEC-81 (`docs/product/decision-log.md`); P-57 (`docs/plan/09-decisions-adrs.md` §9.4.2).
- `docs/plan/epics/A-03.md` §0.1, §3 F1–F3, §4.2 M-A, §7, §11 (R1, R2, R13, QA-4).
- ADR-050, ADR-056, ADR-132, ADR-160, ADR-031; SPEC-540.
