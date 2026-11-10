---
id: TASK-5130
title: "N-04-T22 Live swaps and consumers: NOT manifest, NOT-02 e and f, CLI-05 band and link, POR-02 info row, HOME-01 deadlines"
spec: SPEC-000  # row (N-04-T22)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T22
branch: s29-n04-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
NOT-01, NOT-02 and NOT-03 are live in the manifest; NOT-02 draws e (Collins disagree) and f (Santos no authorization); CLI-05's Open notices band and Open notice analysis link open NOT-02; POR-02 shows a notices info row with no amount or analysis; HOME-01's deadlines open a notice.

## Plan
notices/portal_home.py with `portal_notice_rows` and `open_notice_rows`; portal/home_sources/notices.py; `register_open_notices` hook on organisations, which imports only identity; `DeadlineRowOut.kind`; `TaxProfileOut.open_notice_rows`; new client code `agency_notice_waiting_for_signature`.

## Progress log
- 2026-11-06: built. tests/unit/test_portal_notices_info.py passes (3). NOT-02 e, f and CLI-05 band tests written; held for the end pass. The staging half of the row's check (Whitley journey on live data) stays open: nothing here deployed.

## Decisions made during this task
DEC-2426
