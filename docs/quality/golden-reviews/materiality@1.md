# Materiality engine 1 golden review (CPA memo)

| Field | Value |
|---|---|
| What is reviewed | The materiality engine version 1 (`backend/src/abacus/modules/assurance/compute/materiality.py`; A-04-T08, DEC-1850) and the service that applies it (A-04-T12, DEC-1950) |
| Why | A-04 §6.3 and chapter 10 §10.9.3: the audit CPA confirms the engine's arithmetic before the first real materiality decision. Gates the `assurance.materiality` flip for any real firm |
| Case list | `backend/tests/golden/materiality/northwind_py2025.yaml`, `granite_peak_fy2026.yaml`; SHA-256 over the fixtures in name order: `a83322158fb0294f7f33df6c980333849ca8cb56a62391b8b407e5e32ed8b678` (the test `test_the_cpa_review_names_this_case_list` fails if a fixture changes without this memo) |
| Prepared by | builder (A-04-T17, TASK-2905), Sun Nov 1, 2026 |
| Reviewer | the audit CPA (named in the vault, V-reference; never in git) |
| Status | **review requested; awaiting the CPA's signature**; nothing below is signed |

The memo states what the code computes and where a test pins it; the reviewer checks each line
against AU-C 320 and AU-C 450 and the firm's methodology (BH-EBP-110 step 7), then signs.

## 1. Overall materiality
- `at_rate(amount, rate)`: the benchmark times the rate, rounded to the policy increment (100)
  half up. Northwind: 16,812,400 × 1.5% = 252,186 → **252,200**; at 1.0% **168,100**.
- Golden: `test_ac3_1_ac3_8_options_with_pm_and_ct_from_the_rounded_overall`.
- Reviewer: ☐ rounding the overall to the nearest 100 half up is the firm's convention.

## 2. Performance materiality and clearly trivial
- From the **rounded** overall, to the whole dollar half up: PM 75% = **189,150**, CT 5% =
  **12,610**; Granite Peak 5% of 3,100,000 = **155,000 / 116,250 / 7,750**.
- Reviewer: ☐ PM and CT are taken from the rounded overall, not the unrounded product.

## 3. Benchmark ranges
- Each benchmark's low and high at its range, rounded as in 1: net assets 168,100–336,200;
  contributions 39,500–65,900; benefit payments 24,400–40,600.
- Test: `test_ac3_1_northwind_benchmarks_and_ranges`.
- Reviewer: ☐ the ranges shown beside each benchmark are computed as the firm intends.

## 4. Prior years and growth
- Prior years at the rate (14,228,500 → 213,400; 11,902,700 → 178,500); growth on the first prior
  year to one decimal half up (16,812,400 ÷ 14,228,500 − 1 = **18.2%**). Prior years never move
  today's thresholds.
- Test: `test_ac3_2_prior_years_and_growth_never_move_todays_thresholds`.
- Reviewer: ☐ showing prior years at the current rate, and the growth basis, are acceptable.

## 5. Reassessment at the final basis
- The Final layer at the decided rate, the signed difference from the decided overall and its
  percent of it, one decimal half up: 16,861,000 → **252,900**, **+700**, **0.3%**. The partner
  records No change or Revise; nothing is revised by code.
- Test: `test_ac3_6_the_final_basis_at_the_decided_rate_is_no_change_by_700`.
- Reviewer: ☐ the reassessment comparison is the one AU-C 450 asks the firm to make.

## 6. Options
- The card's options are the bottom of the firm range and its midpoint (1.0% and 1.5% for
  1.0%–2.0%; 3% and 5% for 3%–7%), plus a rate the proposer types inside the range. The engine
  refuses any rate, PM or CT outside the policy.
- Reviewer: ☐ offering the low and the midpoint as defaults is acceptable for the firm.

Signature: ______________________ (the audit CPA)   Date: __________
