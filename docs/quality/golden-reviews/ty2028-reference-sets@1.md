# TY2028 reference sets review (CPA and counsel memo)

| Field | Value |
|---|---|
| What is reviewed | The TY2028 drafts of `due_date_rules`, `form_8879_set` (with the Pub 1345 tolerances), `information_return_thresholds` (payment year 2028) and `legal_holidays` (2028 and 2029, now with the pilot states' own holidays), written by `abacus_tools.refdata_rollover` outside the repository (RB-62 §1) |
| Why | T-08-T24 and DEC-76: reference sets are published by two people only after a CPA (and, for the 8879 set, counsel) confirms them; DEC-85's tolerances are re-verified each season and never defaulted. State due dates now roll on the pilot states' holidays (K-02 QK-5, T-03 R19; DEC-5919) |
| Drafts | named by file and SHA-256 in the table below when written (the drafts themselves never enter a commit) |
| Prepared by | builder (T-08-T24, TASK-8917), Mon Nov 23, 2026 |
| Reviewers | the tax CPA; counsel for §2 (both named in the vault, V-reference; never in git) |
| Publish | staging, then production by Thu Nov 30, 2028, two-person (both founders' handles), no deploy |
| Status | **review requested; awaiting the CPA's and counsel's signatures**; nothing below is signed |

## 1. Due-date rules (TY2028)
- Rolled from the TY2027 set in effect (`refdata_rollover --kind due_date_rules --key us-due-date-rules-ty2027 --to-year 2028`), rows unchanged: offsets from the period end.
- With Sun Apr 15, 2029 and Mon Apr 16 DC Emancipation Day, a calendar-year **Form 1040 is due Tue Apr 17, 2029** (IRC § 7503); 1065 and 1120-S Thu Mar 15, 2029, extended Mon Sep 17, 2029; 1041 extended Mon Oct 1, 2029; Q4 1040-ES Tue Jan 16, 2029 (Mon Jan 15 MLK Day); a 990 for FYE Jun 30, 2028 Wed Nov 15, 2028, extended Tue May 15, 2029; a calendar-2028 Form 5500 Tue Jul 31, 2029, Form 5558 to Mon Oct 15, 2029 (AC2.12; T-08-T25 transcribes the goldens).
- CPA: ☐ no form's original or extended rule changed in law for TY2028; ☐ the installment months.

## 2. The 8879 set and Pub 1345 tolerances (TY2028)
- Rolled from TY2027 (`--kind form_8879_set --key us-form-8879-set-ty2027 --to-year 2028`): each row to tax year 2028 with its TY2027 form and revision; the tolerances carry over **only to be re-verified** (DEC-85).
- CPA: ☐ each authorization form and revision for TY2028. Counsel: ☐ the relock tolerances for the season.

## 3. Information-return thresholds (payment year 2028)
- Rolled from payment year 2027 (`--kind information_return_thresholds --to-year 2028`); the amounts carry over for review.
- CPA: ☐ each threshold against the IRS instructions for payment year 2028, the 1099-NEC and 1099-MISC threshold in particular (raised to 2,000 from payment year 2026 and indexed for inflation after 2026).

## 4. Legal holidays (2028 and 2029) with the pilot states
- Federal and DC from 5 U.S.C. 6103 and D.C. Code § 1-612.02 at observed dates (2029: Jan 1, Jan 15, Jan 20 Inauguration Day (DC; a Saturday), Feb 19, Apr 16 DC Emancipation Day, May 28, Jun 19, Jul 4, Sep 3, Oct 8, Nov 12 Veterans Day observed, Nov 22, Dec 25).
- **New: the pilot states' own holidays** (`--states CO,IL,NY`), counted only for that state's due dates: Illinois (5 ILCS 490) Lincoln's Birthday, Casimir Pulaski Day, General Election Day in an even year; New York (Gen. Constr. Law § 24) Lincoln's Birthday, Election Day; Colorado (C.R.S. 24-11-101) Cesar Chavez Day, Frances Xavier Cabrini Day. 2028: Fri Feb 11 (IL, NY; observed), Mon Mar 6 (IL), Fri Mar 31 (CO), Mon Oct 2 (CO), Tue Nov 7 (IL, NY). 2029: Mon Feb 12 (IL, NY), Mon Mar 5 (IL), Fri Mar 30 (CO; observed), Mon Oct 1 (CO), Tue Nov 6 (NY).
- A federal date never rolls on a state holiday, and a state's date counts the federal holidays and its own (`practice.due_dates.counted`): an Illinois IL-1040 due Sun Apr 15, 2029 rolls to Mon Apr 16 (DC Emancipation Day is not an Illinois holiday), the federal 1040 to Tue Apr 17.
- CPA: ☐ each date against OPM's schedule, the DC list and each state's statute; ☐ how each state treats a holiday on a weekend (the drafts observe Saturday on Friday and Sunday on Monday, as federal).

## 5. Not covered
- Disaster postponements: published as IRS notices arrive, not at the rollover.
- States other than the pilot states: their due dates roll on federal and DC holidays until their calendars are drafted.

## Drafts and sign-off

| Draft file | SHA-256 | Reviewer | Date | Vault reference |
|---|---|---|---|---|
| `legal_holidays-2028.draft.json` (written 2026-11-23, outside the repo) | `b4218a5230fbec240a79fecfef74b2fe32103b4785fffe1e2f45fbb7cab35ecf` | | | |
| `legal_holidays-2029.draft.json` (written 2026-11-23, outside the repo) | `3a4a499aa19ee614d684bc7f78b966d16f5b2d1688d57129500ee7b882eccea6` | | | |
| `due_date_rules-2028.draft.json` | written by the operator from the published TY2027 set | | | |
| `form_8879_set-2028.draft.json` | written by the operator from the published TY2027 set | | | |
| `information_return_thresholds-2028.draft.json` | written by the operator from the published payment-year 2027 set | | | |
