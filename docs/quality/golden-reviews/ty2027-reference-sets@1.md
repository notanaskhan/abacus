# TY2027 reference sets review (CPA and counsel memo)

| Field | Value |
|---|---|
| What is reviewed | The TY2027 drafts of `due_date_rules`, `form_8879_set` (with the Pub 1345 tolerances), `information_return_thresholds` (payment year 2027) and `legal_holidays` (2028), written by `abacus_tools.refdata_rollover` outside the repository (RB-62 §1) |
| Why | T-03-T18 and DEC-76: reference sets are published by two people only after a CPA (and, for the 8879 set, counsel) confirms them; DEC-85's tolerances are re-verified each season and never defaulted |
| Drafts | named by file and SHA-256 in the table below when written (the drafts themselves never enter a commit) |
| Prepared by | builder (T-03-T18, TASK-6004), Sat Nov 7, 2026 |
| Reviewers | the tax CPA; counsel for §2 (both named in the vault, V-reference; never in git) |
| Status | **review requested; awaiting the CPA's and counsel's signatures**; nothing below is signed |

## 1. Due-date rules (TY2027)
- The rows carry over from TY2026: offsets from the period end, so a calendar-year Form 1040 reads
  Apr 15 and, with Saturday Apr 15, 2028 and Mon Apr 17 DC Emancipation Day (observed), falls due
  **Tue Apr 18, 2028** (IRC § 7503). Extension and installment offsets carry over too.
- CPA: ☐ no form's original or extended rule changed in law for TY2027; ☐ the installment months.

## 2. The 8879 set and Pub 1345 tolerances (TY2027)
- Each return type's row moves to tax year 2027 with its TY2026 authorization form and revision,
  and the tolerances carry over **only to be re-verified** (DEC-85).
- CPA: ☐ each authorization form and revision for TY2027.
- Counsel: ☐ the relock tolerances for the season.

## 3. Information-return thresholds (payment year 2027)
- Each form's threshold and minimum count carry over from payment year 2026 for review.
- CPA: ☐ each threshold against the IRS instructions for payment year 2027.

## 4. Legal holidays (2028)
- Computed from 5 U.S.C. 6103 and D.C. Code § 1-612.02, at observed dates: Fri Dec 31, 2027
  (New Year's Day, observed), Jan 17, Feb 21, Apr 17 (DC Emancipation Day, observed), May 29,
  Jun 19, Jul 4, Sep 4, Oct 9, Nov 10 (Veterans Day, observed), Nov 23, Dec 25.
- CPA: ☐ each date against OPM's schedule and the DC government's list.

## 5. Not covered
- Pilot-state due dates: not a kind yet (`Jurisdiction` is US or DC). Recorded as not modelled.
- Disaster postponements: published as IRS notices arrive, not at the rollover.

## Drafts and sign-off

| Draft file | SHA-256 | Reviewer | Date | Vault reference |
|---|---|---|---|---|
| `legal_holidays-2028.draft.json` (written 2026-11-07, in the ops folder outside the repo) | `2491175a16dd54a1587986f7ae4f49b324614c02313128612b2bd72e40d087b5` | | | |
