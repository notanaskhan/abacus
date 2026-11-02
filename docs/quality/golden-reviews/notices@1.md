# Notices compute 1 golden review (CPA memo)

| Field | Value |
|---|---|
| What is reviewed | The notices compute library version 1 (`backend/src/abacus/modules/notices/compute/`; N-04-T04, DEC-2053) and its PROTECTED parameter files `notice_types.yaml` and `rate_schedules/ty2023.yaml`, `ty2024.yaml`, `ty2025.yaml` |
| Why | N-04 §4.2 (DEC-76 second category): the tax CPA confirms the parameters and the arithmetic before any real notice is analyzed. Gates the `notices.workspace` flip for any real firm |
| Case list | `backend/tests/unit/notices/test_n04t04_compute_goldens.py` (Whitley, Collins, Santos and the index bands) |
| Prepared by | builder (N-04-T04, TASK-3003), Mon Nov 2, 2026 |
| Reviewer | the tax CPA (named in the vault, V-reference; never in git) |
| Status | **review requested; awaiting the CPA's signature**; nothing below is signed |

## 1. Rate schedules (bracket check only, QN-3)
- TY2023, TY2024 and TY2025 ordinary-income brackets for single, MFJ, MFS and HOH (QSS uses MFJ),
  rates 10/12/22/24/32/35/37%. The check verifies the agency's figure; it never replaces it.
- Golden: TY2024 MFJ tax(148,600) = **22,798.00**, tax(151,720) = **23,484.40**, change **686.40**
  = 22% × 3,120 (Whitley).
- Reviewer: ☐ each bound matches the year's IRS inflation adjustment.
- Reviewer: ☐ a change with qualified dividends or capital gains reads "Not checked — preferential rates".

## 2. Underreporter comparison
- Rows by line key: the return as filed, the agency's corrected figure, the difference. The
  difference is explained when the information returns missing from the return foot to the
  income lines' difference (Whitley: 1,870.00 + 1,250.00 = 3,120.00 = 3,532.00 − 412.00).
- Collins: the 1099-B sale is on the return's Form 8949 with 13,200.00 basis, so nothing is
  unreported and the difference is not explained by the information returns.
- Reviewer: ☐ the income lines that information returns may explain are the right set.

## 3. Footing, windows and clocks
- Tax + interest + penalty = total; interest and penalty are the notice's (Whitley 686.40 + 66.61 = **753.01**).
- Respond-by windows: CP2000 30 days, CP14 21, CP3219A 90; CP501, CP503, CP504 and state notices
  are not checked.
- Follow-up: sent date + 60 calendar days, never rolled (Sep 17 → **Nov 16, 2026**).
- Reviewer: ☐ the windows match the agency's practice; ☐ the follow-up convention is the firm's.

Signature: ☐ ______________________ (tax CPA) · date ________
