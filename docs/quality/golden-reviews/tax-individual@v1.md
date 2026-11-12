# Individual return engines v1 golden review (CPA memo)

| Field | Value |
|---|---|
| What is reviewed | The T-04 individual return engines (`backend/src/abacus/modules/tax/compute/individual/`: residency and allocation, the other-state credit, the IT-225 add-backs, the residency rules, the §199A QBI deduction, outside basis, K-1 state sourcing, the partner's PTET shares, the Sch E – K-1 matrix, the Form 1040 leadsheet lines and IT-201's derived lines) and their parameters (`parameters/ty2025.yaml`, `parameters/ty2027.yaml`) |
| Why | T-04 §4.4 and chapter 10 §10.9.4: the tax CPA confirms what the engines compute before a real firm relies on the review workspace (TAX-04 to TAX-07, TXI-01 to TXI-03). Until this memo is signed, `make entitlement` refuses Tax Returns to a firm that isn't synthetic (T-04-T49; DEC-4524) |
| Case list | `backend/tests/golden/tax_individual/feld_ty2025.yaml` (the Feld 2025 goldens) and `backend/tests/unit/tax/test_t04t53_hardening.py`'s boundary cases; SHA-256 of `feld_ty2025.yaml`: `df29a3e001a0071ee7ffbb2a16082c4f41bf72b5eeec41627a9e57be496f8f58` |
| Parameters | TY2025 (`ty2025.yaml`, `reviewed_by: null` until signed); TY2027 carries TY2025's values where the year's figures are not yet published (T-04-T11), each such value an exception below |
| Signature record | `backend/src/abacus/modules/tax/compute/individual/parameters/review.yaml` (`signed: false`); `review_signed()` reads it and `make entitlement` refuses without it |
| Engines (each `requires_review`) | `review.ENGINES`: residency.allocation, residency.it112r, residency.it225, residency.rules, k1.qbi_199a, k1.outside_basis, k1.state_sourcing, k1.ptet_share, k1.sch_e_matrix, leadsheets.form_1040, worksheets.it201 |
| Prepared by | builder (T-04-T49, TASK-7524), Thu Nov 12, 2026 |
| Reviewer | the tax CPA (named in the vault, V-reference; never in git) |
| Status | **review requested; awaiting the CPA's signature**; nothing below is signed |

The memo states what the code computes and where a golden test pins it. The reviewer checks each
line against the Code, the regulations and the firm's methodology, ticks it, and signs. On
signature: `review.yaml` reads `signed: true` with the date and the vault reference,
`ty2025.yaml` names the reviewer's V-reference in `reviewed_by`, and this Status line reads
**signed**. The engine of record computes tax (DEC-77, ADR-231): these engines are the review
workspace's own arithmetic only.

## 1. Residency and allocation (TXI-03)
- Allocation: the federal amounts the state return starts from, summed: 268,400 + 6,910 + 14,820 +
  307,900 = **598,030**.
- Residency rules: more than `statutory_days` (183) in New York City with a permanent place of
  abode there is full-year State and City (NY Tax Law §605(b)(1)(B)); fewer, with the main home
  elsewhere, is a conflict a person resolves. Feld: 281 days with a City abode → full-year, no
  conflict; the 150-day Rhinebeck variant → a conflict. Exactly 183 days is not "more than".
- Tests: `test_residency_rules_at_every_boundary`, `test_allocation_and_it225_foot`.
- Reviewer: ☐ the statutory-day test and the abode condition, ☐ the conflict rule.

## 2. Other-state credit (IT-112-R) and add-backs (IT-225)
- Credit = min(other state's tax, NY tax × other-state income / NY AGI), the limit half up to the
  dollar: min(11,279, 41,070 × 238,623 / 615,605 = **15,920**) = **11,279**; NYC takes no
  other-state credit. A zero NY AGI refuses.
- IT-225 add-backs: 4,746 + 11,279 = **16,025**.
- Tests: `test_it112r_takes_the_lesser_and_refuses_a_zero_agi`.
- Reviewer: ☐ the limit formula and its rounding, ☐ the add-back set.

## 3. K-1 treatments (TXI-02)
- §199A: 20 % of QBI against max(50 % of W-2 wages, 25 % of W-2 wages + 2.5 % of UBIA): Ridgeline
  307,900 → tentative **61,580**, limit **98,450** (UBIA 3,938,000, W-2 wages 0), deduction 61,580.
  At the limit, the deduction is the limit.
- Outside basis: tax capital + the §752 liability share: 1,912,500 + 2,762,075 = **4,674,575**.
- State sourcing by property percentage, whole dollars by largest remainder: IL 46.0 % / CO 31.5 %
  / NY 22.5 % → 141,634 + 96,989 + 69,277 = **307,900**.
- PTET: the partner's 25 % of each entity PTET, each half up: 7,011 + 4,268 + 4,746 = **16,025**.
- Tests: `test_qbi_*`, `test_outside_basis_adds_the_liability_share`,
  `test_state_sourcing_foots_by_largest_remainder`, `test_ptet_shares_round_each_half_up`.
- Reviewer: ☐ the §199A arms and the threshold treatment, ☐ the §752 share, ☐ the sourcing
  convention, ☐ the PTET share and rounding.

## 4. Leadsheets and IT-201
- A Form 1040 leadsheet line is the sum of its contributing approved fields.
- IT-201: line 33 = line 19 + line 20 + line 22; line 37 = line 33 − line 34; total tax = the
  imported NY and NYC tax (the engine of record's); balance due and overpayment from payments.
- Tests: `test_a_leadsheet_line_sums_its_parts`, `test_it201_*`.
- Reviewer: ☐ the line derivations, ☐ that NY and NYC tax stay imports.

## 5. Exceptions
- TY2027 parameters that repeat TY2025 values until the year's figures are published (T-04-T11):
  each is listed in `ty2027.yaml` with its source note; the CPA signs them or names a replacement.
- Rounding: whole dollars half up everywhere except state sourcing (largest remainder, so the
  shares foot exactly).
