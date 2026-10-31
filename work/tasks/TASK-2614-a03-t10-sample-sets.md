---
id: TASK-2614
title: A-03-T10 sample-set service, SampleDrawWorkflow, override and L2 approval
spec: SPEC-580
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T10
branch: s21-a03-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Marcus cannot approve a version Marcus prepared, Hannah's approval writes one L2 sign-off and
sample_set.approved and supersedes the earlier approved version, and an untied population answers
409 population_not_tied." (A-03 §3 F3; ADR-340 §5 to §8.)

## Scope
**In**: K-02's new threshold-policy kind `attribute_sample_sizes` (payload, import list field,
deterministic `attribute_sample_size`, `methodology.api.attribute_sample_size` for the firm's
table in effect); `sampling/sample_sets.py` (create, start a draw with a server seed and the
`Idempotency-Key`, picker, projection, draw progress, items search and pages, approval, the
deterministic export with formula text kept as text); `sampling/draw.py` with
`SampleDrawWorkflow` (`sample_draw.run`, `sample_draw.fail`) and its v1 replay histories;
`register_reviewable('sample_set_version')` with its facts (L1 preparer, L2 approval), gate kind
`sample_set_approval`, C16 `sample_set_approval_requested` to the engagement's leads, audit
owners for `population`, `sample_set`, `sample_set_version`, the reviewed activity fallback rows,
the Fieldwork › Sample Selection rail row declared in `sampling/registry.py` and registered by
assurance. Contract: create answers `SampleSetCreatedOut`; every route but T13's is live.
**Out (DEC-1662)**: the rail row's version child rows (SectionState has no child rows yet); the
AUD-03 Sample-driven band source (T13 writes the requests it groups); `sample_version_view` and
`approved_items` in `sampling.api` (T13 is their first consumer); the parameters' program-step
citation (the size table's version is cited; the K-01 step citation lands with A-03-T16's seed);
the population label from the evidence file name ("census v2"; the record unit shows).

## Plan
1. [x] Size table kind and function. 2. [x] Repository, service, draw, workflow, activities.
3. [x] Contract routes, registrations, catalogue, rail row, audit owners. 4. [x] Tests: unit
(size table, inputs hash parity with the sampler, strata counts, ties, export bytes, seed rule),
HTTP (draw, replay, AC-1 to AC-3, override, stale hash, search and export, walls), replay.
Rollback: revert the PR; no migration (0520 holds every table).

## Progress log
- 2026-10-31: built; tests written first, run at the batch's end review.
