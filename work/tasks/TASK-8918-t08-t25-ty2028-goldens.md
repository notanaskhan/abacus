---
id: TASK-8918
title: "T-08-T25: I-CLOCKS golden fixtures for TY2028 and the HOME-03 seed dates"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T25
---

## Objective
Row: "I-CLOCKS golden fixtures for TY2028 and the HOME-03 seed dates, transcribed by the non-implementer for tax CPA review." Acceptance: "Goldens prove Apr 17, 2029, Jan 16, 2029, Sep 17, 2029, Oct 1, 2029, Mar 16, 2026 and Nov 16, 2026, and the tax CPA signs them."

## Done
- tests/golden/calendar/i_clocks_ty2028.yaml: 2026–2029 federal and DC holidays, rules, 9 due-date cases and 4 installments, each with its source
- tests/golden/test_t08t25_ty2028_goldens.py (15 pass): every case, the six acceptance dates proven, the holiday drafts equal the goldens
- review memo §1 names the file for the CPA's signature; DEC-5920

## Progress log
- `2026-11-23` — Built in full. Human remainder: the tax CPA signs each case in the TY2028 review memo.
