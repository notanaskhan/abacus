---
id: SPEC-580
title: A-03 sampling engine and TB mapping, S20 foundations (bundle, kernel, sampler v2.3, contract stubs, migrations, taxonomy)
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-050, ADR-089, ADR-090, ADR-132, ADR-160, ADR-340, ADR-341]
related_specs: [SPEC-037, SPEC-316, SPEC-540]
created: 2026-10-30
updated: 2026-10-30
---

> **Instructions for coding agents**
> - This is A-03's own SPEC (created at the S20 kickoff, as SPEC-540 promised). It carries the S20
>   rows: T01, T21, T04, T02, T05, T03, T06 and T22. Later rows (T07–T20) add their ACs here.
> - ADR-340 (P-57) and ADR-341 (P-63) bind every row. ADR-341 §5 replaces the plan's stored
>   `account_mappings` and `account_mapping_events` (A-03 §4.2 M-B): rule mappings are computed on
>   read and people's edits stay insert-only in `mapping_set_edits` (migration 0079, SPEC-316).

## 1. Summary
The S20 slice of A-03 "Sampling & TB mapping": the protected bundle, the compute kernel the
import-linter contract names, the frozen sampler library v2.3, the two contract stubs (sampling and
C9 v2), the sampling migration, the remaining taxonomy work, and the consumer contract tests.

## 2. Problem and context
Parts of A-03 were built ahead of plan: journal-entry selection (`seeded_v1`, SPEC-037, ADR-132),
populations over ledger snapshots (TASK-083), and the first slice of account mapping (SPEC-316,
migration 0079: grouping sets with draft and published versions, rule mappings computed on read,
insert-only edits, L1/L2 sign-offs). S20 builds the foundations the S21–S23 screens and services
stand on. `docs/plan/epics/A-03.md` §0, §3, §4, §8, §9.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Marcus Delgado (senior) | Builds populations, draws versions, generates item requests |
| Hannah Leclerc (manager) | Approves a sample version (L2), never one Marcus prepared for her |
| Caleb Dunn (senior) | Runs, edits and confirms the account mapping |
| Margaret (quality partner) | Imports and publishes the firm's grouping set with fresh MFA |
| The Accrued Agent, support, portal principals | Read at most (agent at task scope); never write |

## 5. Acceptance criteria
- **AC-1** (A-03-T01) Every A-03 write (`population.create`, `sample_set.create/approve/export/
  generate_requests`, `grouping_set.import/publish`, `mapping_set.run/confirm/edit`,
  `account_mapping.edit`) denies the agent, support and every portal principal; the system holds
  only `mapping_set.run`. The generated permission suites carry the cases.
- **AC-2** (A-03-T01) `sample_set.approve` carries `not_preparer_of_target`; `grouping_set.publish`
  needs a fresh second factor and is listed in `fresh-mfa-actions.yaml`.
- **AC-3** (A-03-T01) Flags `sampling.sample_sets` and `ledger.tb_mapping` exist, default off.
  `sampling` may import `methodology`, `review` and `requests`; the graph stays acyclic; `ledger`
  keeps an empty dependency set.
- **AC-4** (A-03-T21) `kernel.numeric`: a Decimal context at precision 28, `quantize_half_up`, and
  `allocate(total, weights, places)` (largest remainder, optional per-share half-up) whose shares
  always foot to the total (Hypothesis).
- **AC-5** (A-03-T21) `kernel.calendar`: `is_business_day`, `roll` and `add_business_days` over a
  holiday set passed in; no holiday data in the kernel (DEC-76). `practice/compute/calendar.py`
  re-imports them and K-02's I-CLOCKS goldens pass unchanged.
- **AC-6** (A-03-T21) The import-linter contract "compute packages import only kernel.numeric and
  kernel.calendar" is on for `sampling/compute` and `ledger/compute`; any other import fails.
- **AC-7** (A-03-T04) `select()` v2.3 gives byte-identical items (and `items_hash`) for the same
  seed, canonical population and version; every output carries `engine_version` and `inputs_hash`.
- **AC-8** (A-03-T04) `attribute_size(0.90, 0.10, 0)` is 22; `udl(0, 25, 0.90)` is 8.8% and
  `udl(2, 25, 0.90)` is 19.9% (exact binomial, ROUND_HALF_UP to one decimal for display);
  `projected_misstatement(2140, 25, 412)` is 35,267.20 (ratio estimate; QA-3 keeps the display rounding open).
- **AC-9** (A-03-T04) Code under `sampling/compute/` references no `random` member other than
  `Random` and `getrandbits`; `SAMPLER_VERSIONS` registers `2.3` frozen.
- **AC-10** (A-03-T04) Strata partition the population (Σ counts = N, Σ amounts = total); a
  selection is a subset without duplicates; threshold strata take every item at or above the top
  threshold and none below the floor.
- **AC-11** (A-03-T02) The sampling API stub: classified Pydantic models and every A-03 §4.3
  sampling route; 404 with `sampling.sample_sets` off, Brightwater Hale fixtures (or 501 for
  writes) with it on; the generated client exposes every operation.
- **AC-12** (A-03-T02) Status registry families `sample_set_version` (drawing, draft, approved,
  superseded, failed) and `completeness_tie_result` (tie, off, check) regenerate the StrEnums and
  `status.ts`; screen contracts `docs/screens/AUD-11.md`, `AUD-31.md` and the SHL-14 c addendum
  record DV-A1–A4, DV-B1–B3 and DV-C1.
- **AC-13** (A-03-T05) The sampling migration (populations, population_records,
  completeness_ties, sample_sets, sample_set_versions, sample_strata, sample_items) passes
  up/down/up with forced RLS and its tables are registered (owners, insert-only).
- **AC-14** (A-03-T05) A frozen version refuses any change but its permitted status moves (draft →
  approved | superseded, approved → superseded) and the approval stamps; a non-human approval write
  and an approval without an approver are refused by the database; one approved version per set.
- **AC-15** (A-03-T05) `threshold_policies.kind` accepts `attribute_sample_sizes`.
- **AC-16** (A-03-T03) The C9 v2 stub: models for grouping sets, groupings, FS lines, mapping sets
  on the TB of record, account mappings, tallies and the mapped trial balance; assurance-hosted
  routes behind `ledger.tb_mapping` with Granite Peak 128-account and BH FS groupings v1 fixtures;
  the reserved adopt route is declared in `docs/contracts/ledger-mapping.md` only.
- **AC-17** (A-03-T06) An import with an overlapping number range returns its row problem
  (`overlapping_range`, sheet, row, code); a clean import has zero problems; publish is a person's
  with fresh MFA (`published_actor_kind = 'human'`); `ledger.api.grouping_catalogue` and the picker
  read with the viewer's "Recently used"; `ledger` keeps an empty dependency set.
- **AC-18** (A-03-T22) Consumer contract tests (pytest against the stubs, TypeScript fixture
  assertions for AUD-11 and AUD-31) fail on any breaking change to the Granite Peak 128-account or
  BH FS groupings v1 shapes.

## 6. Open questions
- QA-3 (display rounding of the projection, "$35,300" against 35,267.20) stays open until the
  golden case (A-03-T09); no test "fixes" it.
