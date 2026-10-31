---
id: TASK-2502
title: A-03-T04 sampler compute library v2.3 (verify-and-complete)
spec: SPEC-580
acceptance_criteria: [AC-7, AC-8, AC-9, AC-10]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T04
branch: s20-a03-t04
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The frozen sampler library ADR-340 decides, in `sampling/compute/`: canonical order and hash, the
one RNG primitive, version 2.3's three methods, the size, limit and projection helpers, and the
version registry.

## Verify first (status: partial)
`sampling/selection.py` holds `seeded_v1` (journal entries, ADR-132: `random.Random(seed).random()`
and a partial Fisher–Yates). It has no canonical population hash, no `getrandbits` primitive, no
strata, no `attribute_size`, `udl` or `project`, no version registry. Kept unchanged (ADR-340 §3);
everything below is new.

## Plan (amber)
- `compute/canonical.py`: `Record`, `normalise_key` (NFKC, trim, casefold; no blank or control
  characters), `canonical()` (sorted, duplicates and mixed amounts refused, SHA-256 of JSON lines).
- `compute/draw.py`: `Stream(seed)` (24-bit), rejection sampling on `getrandbits(32)`,
  `partial_fisher_yates` over a sparse swap map.
- `compute/v2_3.py`: `select()` for `attribute_nonstatistical`, `attribute_statistical`,
  `threshold_random_stratified` (min inclusive, max exclusive; all/random/none); `inputs_hash`,
  `items_hash`, `engine_version`.
- `compute/stats.py`: `binomial_cdf`, `attribute_size`, `udl`, `udl_percent`, `projected_misstatement`,
  `projected_misstatement_ratio` in `kernel.numeric`'s context.
- `compute/versions.py`: read-only `SAMPLER_VERSIONS` with `2.3` frozen; `sampler(id)`.
- `sampling.api` re-exports `attribute_size`, `udl`, `udl_percent`, `projected_misstatement`, `SAMPLER_VERSIONS`,
  `SAMPLER_CURRENT` (A-03 §4.3 module API). README section.
- Not here: the golden corpus and the designed Northwind/Granite Peak fixtures (T09, T16: built by
  inverse construction so the honest algorithm lands on the designed lists).
- Rollback: revert; nothing reads the library yet.

## Acceptance
| Check | Test |
|---|---|
| Byte-identical items for same seed, population and version | `test_ac7_*` |
| 22 · 8.8% · 19.9% · 35,267.20 | `test_ac8_the_designed_size_limits_and_projection` |
| Only `Random` and `getrandbits` from `random`; 2.3 frozen | `test_ac9_*` |
| Strata partition, threshold all/none, 24 + 16 | `test_ac10_*`; `tests/property/sampling/test_a03t04_properties.py` |

## Progress log
- 2026-10-30: built (smoke: 22, 8.8, 19.9, 35267.20 printed from the library). Tests run at the
  end review. DEC-1552.
