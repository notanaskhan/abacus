# EBP engines 1 golden review (CPA memo)

| Field | Value |
|---|---|
| What is reviewed | The EBP engines (`backend/src/abacus/modules/assurance/compute/ebp/`: plan status, provisions, eligibility, remittance, loans and distributions, trust agreement, participant accounts, expenses and limits) and their reference parameters (`reference/irc_6621_rates.yaml`, `reference/irs_plan_limits.yaml`) |
| Why | A-05 §4.9 and chapter 10 §10.9.4: the audit CPA (EBP) confirms what the engines compute before a real firm uses EBP-01 to EBP-06. The `ebp_audits` entitlement refuses a non-synthetic firm until this memo is signed (A-05-T49; ADR P-28) |
| Case list | `backend/tests/golden/ebp/northwind_py2025.yaml`, `northwind_py2025_slice2.yaml`; SHA-256 over the names and fixtures in name order: `0c39d7c51760bd53be4d5712e90be08a38a75ee381b135509b851bb482af6495` (`test_the_cpa_review_names_this_case_list` fails if a fixture changes without this memo) |
| Signature record | `backend/src/abacus/modules/assurance/compute/ebp/reference/review.yaml` (`signed: false`); the entitlement reads it, and a test keeps it and this Status line in step |
| Prepared by | builder (A-05-T49, TASK-6003), Sat Nov 7, 2026 |
| Reviewer | the audit CPA (EBP) (named in the vault, V-reference; never in git) |
| Status | **review requested; awaiting the CPA's signature**; nothing below is signed |

The memo states what the code computes and where a golden test pins it. The reviewer checks each
line against the plan document, DOL and IRS rules and the firm's EBP methodology, ticks it, and
signs. On signature: `review.yaml` reads `signed: true` with the date and the vault reference,
`irs_plan_limits.yaml` and `irc_6621_rates.yaml` name the reviewer's V-reference in `reviewed_by`,
and this Status line reads **signed**.

## 1. Plan status (EBP-01)
- Filer status from participants with account balances at the beginning of the year (Form 5500
  instructions): Northwind PY2025 286 at BOY, 301 at EOY, so a large-plan filer needing an audit.
- Census, W-3 and payroll foot to the cent: W-3 Box 1 13,813,400.00 + Box 12 D 746,600.00 =
  **14,560,000.00**.
- Tests: `test_ebp01_plan_profile_figures`, `test_census_w3_and_payroll_foot_to_the_cent`.
- Reviewer: ☐ the filer-status count and the compensation footing are the firm's convention.

## 2. Provisions (EBP-02)
- The twenty provisions that affect the statements (AU-C 703), each compared document to
  operation; the registry is code, the answers are people's.
- Reviewer: ☐ the twenty provisions are the ones the firm tests for a QACA safe-harbor plan.

## 3. Eligibility (EBP-03)
- Entry on the first of the month after the later of age 21 and hire plus 3 months; automatic
  enrollment at 6 % escalating 1 % a year to 15 %; missed deferral 6 % and missed QACA match
  3.5 % of compensation (EPCRS correction amounts).
- Golden (A-05-T20's acceptance): Kwame missed **2,472** deferral and **1,442** match; Yuki **3,168** and **1,848**; the
  population query (eligible, not enrolled, no opt-out) returns exactly **4**.
- Tests: `test_ebp03_entry_is_the_later_of_age_21_and_three_months`,
  `test_missed_is_idempotent_and_exact`, `test_review_of_matching_dates_needs_none`.
- Reviewer: ☐ the entry rule, ☐ the escalation schedule, ☐ the missed-amount percentages.

## 4. Contributions and remittance (EBP-04)
- A deposit is late after the earliest date it could reasonably be segregated, read as business
  days (29 CFR 2510.3-102): pay date Fri Dec 26, 2025, deposited Fri Jan 9, 2026, **9 business
  days** (10 calendar days), amount **33,540.00**.
- The receivable foots: regular 15,060.00 + late 33,540.00 = **48,600.00**.
- VFCP lost earnings compound daily at each day's IRC §6621(a)(2) quarter rate
  (`irc_6621_rates.yaml`; a missing quarter is a refusal, never a guess).
- Tests: `test_the_late_remittance_is_9_business_days`, `test_the_receivable_foots`.
- Reviewer: ☐ business days as the lateness measure, ☐ daily compounding at the quarter's rate,
  ☐ the 2025 and 2026 quarterly rates in the reference file.

## 5. Loans and distributions (EBP-05)
- The loan rollforward foots to the trust report (loans **312,400.00**); new loans meet IRC
  §72(p) (the lesser of 50,000 and half the vested balance; five years unless for a residence,
  where 180 months needs one); offsets total and count in benefits paid (**1,284,600.00**);
  withholding counts the offset.
- Tests: `test_ebp05_the_loan_rollforward_foots_to_the_trust_report`,
  `test_ebp05_new_loans_meet_72p`, `test_ebp05_a_180_month_term_needs_a_residence`,
  `test_ebp05_offsets_total_and_benefits_paid`, `test_ebp05_withholding_counts_the_offset`.
- Reviewer: ☐ the §72(p) limits as coded, ☐ offsets inside benefits paid, ☐ withholding on offsets.

## 6. Trust agreement (EBP-06)
- Each certified trust line agrees to the plan TB line of the same name at both dates; a line not
  certified is held below the certified footing. Net assets: trust **16,812,400** + receivable
  **48,600** = **16,861,000**.
- Tests: `test_ebp06_investments_foot_and_tie_line_by_line`,
  `test_ebp06_a_line_off_by_a_dollar_names_the_difference`,
  `test_ebp06_a_line_not_certified_is_held_below_the_certified_footing`,
  `test_ebp06_net_trust_assets_with_loans`.
- Reviewer: ☐ the limited-scope (ERISA 103(a)(3)(C)) certification treatment of uncertified lines.

## 7. Participant accounts (EBP-08) and expenses and limits (EBP-09)
- Accounts crossfoot by status group to the trust (beginning + contributions + earnings +
  distributions + fees + transfers = ending); vesting is a two-year cliff and an unknown hire date
  stays unknown, never assumed.
- Expenses foot to Schedule H 2i (**38,400** = 2i(1) 6,000 + 2i(2) 32,400); a fee with no 408(b)(2)
  disclosure is an exception; the budget account rolls; PY2025 limits come from
  `irs_plan_limits.yaml` (402(g) 23,500 for 2025, catch-up and the rest as listed there; a missing
  year is a refusal).
- Tests: `test_ebp08_the_groups_crossfoot_to_the_trust`,
  `test_ebp08_vesting_is_two_year_cliff_and_unknown_stays_unknown`,
  `test_ebp09_expenses_tie_to_schedule_h`, `test_ebp09_a_fee_with_no_disclosure_is_an_exception`,
  `test_ebp09_py2025_limits`.
- Reviewer: ☐ the vesting schedule as the plan's, ☐ the limits table against the IRS notices.

## 8. What the engines never do
- No model computes a figure: numbers in agent text are cited values or computed facts (A-05 §6).
- An engine version bump changes every inputs hash, so results computed under the old version read
  out of date (`test_a_version_bump_changes_every_inputs_hash`).

## Sign-off

| Item | Reviewer | Date | Vault reference |
|---|---|---|---|
| Sections 1 to 8 | | | |
