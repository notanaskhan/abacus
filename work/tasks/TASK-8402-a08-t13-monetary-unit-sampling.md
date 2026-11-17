---
id: TASK-8402
title: "A-08-T13: Monetary-unit sampling as a new frozen sampler version"
spec: SPEC-657
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
branch: a08-t13-monetary-unit-sampling
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T13
---

## Objective
Spec section: docs/plan/epics/A-08.md §3 F4. Monetary-unit sampling: sampling/compute/mus.py as a new frozen sampler version (interval from tolerable and expected misstatement and the firm's confidence factors, certainty items, systematic PPS from a seeded start), method monetary_unit on A-03's routes, AUD-11 method option from the DF-05 frame behind sampling.monetary_unit.

## Plan (amber)
1. `sampling/compute/mus.py` (pure, frozen, "mus/1.0"): interval in whole cents rounded down, certainty items, systematic PPS over the rest in canonical order from a seeded start in cents, zero and negative balances excluded; `items_hash`, `inputs_hash`. v2.3 and `SAMPLER_VERSIONS` untouched.
2. `methodology.standards.mus_factors` (firm `mus_confidence_factors` content in effect: zero-error factor, expansion = one-error minus zero-error).
3. `sampling.sample_sets.draw`: method `monetary_unit` behind `sampling.monetary_unit` (404 off), parameters `tolerable_misstatement`, `expected_misstatement`, `confidence`; the expected size and the interval recorded in `parameters.mus`; `sampler_version` "mus/1.0". `draw.run_draw` branches to `_select_mus` and re-checks the inputs hash. `ParametersOut` gains the misstatements and the interval.
4. Migration `0942_mus_reasons.py`: `sample_items.selection_reason` += `certainty`, `pps`.
5. AUD-11: method label, algorithm, misstatement and interval rows; sampler label handles the named version. Generated client regenerated (also carries A-08-T21/T22's contract changes).
6. Tests: `tests/unit/sampling/test_a08t13_mus.py`. Rollback: `alembic downgrade 0941`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5402). Lint, pyright, tsc and eslint clean on touched files. Partial: no MUS artboard exists (DF-05), so no AUD-11 fixture scenario with drawn MUS items is added (it would invent figures; the Granite Peak AR MUS goldens are the end pass's); `final_size` is the expected size the interval implies, and the drawn count is the items' count. Gates and tests run once at the S48 end pass (build first, test last).
