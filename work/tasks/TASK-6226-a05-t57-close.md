---
id: TASK-6226
title: A-05-T57 close, AUD-27's transactions, period dates and excise line
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T57
branch: s31c-a05-t57
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- `aud27.add_party_in_interest` (human-only, `party_in_interest.manage`) and the create route goes live. `Aud27ItemIn` gains, additively, relationship, exemption, reporting and transactions.
- The read returns `transactions`. `Aud27RollforwardOut` gains `opening_on` and `closing_on`, read through `engagements.api.work_item_period` (new). `Aud27ProhibitedOut` gains `excise_exposure`.
- AUD-27 shows the dated rollforward, the 2025 transactions column and the excise sentence.
- EBP-07's 4i matcher also matches a party's first word or initials.
- Tests: `test_a05t57_close.py`, matcher cases in `test_a05t58_close.py`, and `AUD-27.test.tsx`.

## Left
- Related-party activity columns; citation and procedure counts (DV-AUD-27-2, 4).

## Progress log
- 2026-11-08: built; runs at the close end pass.
