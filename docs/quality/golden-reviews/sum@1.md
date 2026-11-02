# SUM engine 1 golden review (CPA memo)

| Field | Value |
|---|---|
| What is reviewed | The SUM engine version 1 (`backend/src/abacus/modules/assurance/compute/sum.py`; A-06-T07, DEC-1964) |
| Why | A-06 §6 and chapter 10 §10.9.3: the audit CPA confirms the engine's arithmetic before the first real SUM conclusion. Gates the `assurance.completion` flip for any real firm |
| Case list | `backend/tests/golden/sum/granite_peak_fy2026.yaml`, `northwind_illustrative.yaml`, `northwind_py2025.yaml`; SHA-256 over the fixtures in name order: `314e2f13bebe96475685b002d3ff5121505619ed5019322ef293ababcd651931` (the test `test_ac_the_memo_names_the_case_list` fails if a fixture changes without this memo) |
| Prepared by | builder (A-06-T08, TASK-3015), Mon Nov 2, 2026 |
| Reviewer | the audit CPA (named in the vault, V-reference; never in git) |
| Status | **review requested; awaiting the CPA's signature**; nothing below is signed |

## 1. Rollover and iron curtain (AU-C 450)
- Rollover: this year's uncorrected effects plus the turnaround of last year's: 35,300 − 1,150 = **34,150**.
- Iron curtain: the year-end effect, cumulative of last year's still uncorrected: 35,300 − 13,050 = **22,250**.
- The aggregate is the larger in absolute value: **34,150**.
- Reviewer: ☐ both views are computed as the firm's methodology requires.

## 2. Percentages and the bar
- 34,150 ÷ 189,150 = **18.1%** of PM; fill 34,150 ÷ 252,200 = **13.5%** of overall; ticks CT 5.0%, PM 75.0%.
- One decimal, half up.
- Reviewer: ☐ the rounding is the firm's convention.

## 3. Clearly trivial and the approaching-PM line
- BCT-1 4,210 under CT 12,610 is listed and never accumulated.
- An illustrative 96,800 is 51.2% of PM: it crosses the firm's 50% line (flagged; the partner concludes).
- Granite Peak AJE-3 68,400 is 58.8% of PM 116,250: approaching, not above.
- Reviewer: ☐ the approaching-PM line and the below-CT rule are applied as intended.

Signature: ☐ ______________________ (audit CPA) · date ________
