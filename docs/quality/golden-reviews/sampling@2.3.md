# Sampler 2.3 golden review (CPA memo)

| Field | Value |
|---|---|
| What is reviewed | Sampler 2.3 (`backend/src/abacus/modules/sampling/compute/`; ADR-340), frozen in `SAMPLER_VERSIONS` |
| Why | A-03 §0 and chapter 10 §10.9.4: the audit CPA signs the sampler's size, limit, projection and stratification before the first real sample. This gates the `sampling.sample_sets` flip on Tue Sep 21, 2027 (RB-46 §C) |
| Prepared by | builder (A-03-T20, TASK-2823), Sun Nov 1, 2026 |
| Reviewer | the audit CPA (named in the vault, V-reference; never in git) |
| Status | **awaiting the CPA's signature**; nothing below is signed |

The memo states what the code computes and where a test pins it. The reviewer checks each line
against professional standards and the firm's methodology, then signs. The golden tests pin the
**computed** values; a display rounds only on screen (DEC-1659).

## 1. Sample size (attribute, statistical)
- `compute.attribute_size(confidence, tolerable_rate, expected_rate)` gives the smallest n whose
  exact binomial upper deviation limit at the confidence is at or below the tolerable rate.
- Golden: 90 % confidence, 10 % tolerable, 0 % expected gives **22**
  (`tests/golden/sampling/test_a03t09_sampler_goldens.py::test_ac3_attribute_size_udl_and_projection_match_the_design`,
  `statistics.yaml`).
- A non-statistical draw takes the firm's published size table (K-02 `attribute_sample_sizes`). A
  smaller size is an override with a rationale and the approver's acknowledgement (A-03-T10).
- Reviewer: ☐ the binomial method and the 22 are right for these parameters.

## 2. Upper deviation limit
- `compute.udl_percent(deviations, size, confidence)` is the exact one-sided binomial upper limit,
  shown as a percent.
- Golden cases: `statistics.yaml` › `udl_percent`, asserted in the same test.
- Reviewer: ☐ exact binomial, one-sided, at the stated confidence, is the limit the firm uses.

## 3. Projected misstatement (display)
- `compute.projected_misstatement(misstatement, sample_count, population_count)` scales a sample's
  misstatement by count: 2,140 over 25 of 412 projects **35,267.20**. The design showed $35,300,
  a rounding of this value (QA-3, DEC-1659); the screen keeps the computed figure.
- Test: `test_ac3_qa3_is_settled_the_golden_pins_the_computed_value_not_the_display`.
- Reviewer: ☐ ratio projection by count is acceptable for this use, and the display rule is right.

## 4. Stratified selection (`threshold_random_stratified`)
- Every item above the upper threshold is taken. Inside the band a uniform draw is made without
  replacement (rejection sampling and a partial Fisher–Yates walk over
  `random.Random(seed).getrandbits(32)`). Below the lower threshold, nothing.
- Golden: Granite Peak's 1,912 disbursements, seed 0x7C31B4. Strata 24 / 1,102 / 786. It takes
  24 + 16 = 40 items totalling 3,698,700 (3,286,400 + 412,300), a 9.6 % value share.
- Tests: `test_ac2_seed_0x7c31b4_draws_24_plus_16_payments_totalling_3698700`,
  `test_ac2_the_strata_foot_24_plus_16_and_3286400_plus_412300`,
  `test_ac2_the_value_share_renders_9_6_percent`, and
  `tests/unit/sampling/test_a03t04_sampler_v2_3.py::test_ac10_threshold_strata_take_all_above_sixteen_inside_and_none_below`.
- Reviewer: ☐ the top stratum is examined in full, and the band is drawn at random and without replacement.

## 5. Randomness and re-performance
- The seed is 24 bits from the server (`secrets`). No request carries one; only the scenario
  loader seeds a synthetic firm (A-03-T10, A-03-T18). Every version records its seed, the
  population's SHA-256, `inputs_hash` and `items_hash`.
- The frozen corpus (`tests/golden/sampling/corpus/v2.3.yaml`, seven cases) pins (seed,
  population, version) to items; Northwind's seed 0x5E2A91 draws the 25 designed participants in
  order.
- RB-46 §A re-performs a sample from its record alone.
- Reviewer: ☐ the record is enough for another auditor to re-perform the selection.

## Sign-off
| Reviewer | Date | Result | Notes |
|---|---|---|---|
| — | — | — | — |
