---
id: TASK-8422
title: "C-01-T58: Close-receipt intake destination"
spec: SPEC-655
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
branch: c01-t58-close-receipt-destination
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T58
---

## Objective
Spec section: docs/plan/epics/C-01.md §0 (INB-02 b, N-01 DV-7). Register the close_receipt destination kind on communications.api.register_intake_destination: its resolver lists the client's open close-intake requests and card-charge candidates from the C9 v2.1 ledger read API; filing lands in the close's intake; fails closed with closes.engine off; an agent context is refused.

## Plan (amber)
1. `closes/intake_destination.py`: nodes — the client's open closes (`close_receipt`, has children); under a close, its open intake requests (`request` nodes, communications' own placement fulfils them in the intake binder) and the period's newest card charges (credit-card accounts' register lines, information nodes `card_charge_candidate`, not selectable); placement — a person only, `closes.engine` on, an open close → its engagement and work item.
2. Registered from `closes.api`.
3. Tests: `tests/unit/closes/test_c01t58_close_receipt.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5414). Lint and pyright clean; app and worker import. Partial: the charge candidates are the period's newest card charges, not matched to the receipt (the picker's resolver gets no attachment, so no amount to match); the staging walk with Grace's Copperleaf receipt is a human step. Gates and tests run once at the S48 end pass (build first, test last).
