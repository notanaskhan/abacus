---
id: TASK-8506
title: "C-02-T07: Closes-delivery contract stub and SPEC-701 CAS deliverables, hand-off and information returns"
spec: SPEC-701
acceptance_criteria: [AC-5, AC-8, AC-19]
risk_zone: amber
status: in-review
branch: c02-t07-closes-delivery-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T07
---

## Objective
Spec section: docs/plan/epics/C-02.md §3 F7–F9, §4.3. SPEC for CAS deliverables, hand-off and information returns; models and 501 routes behind closes.delivery, closes.tax_handoff and closes.information_returns; docs/contracts/closes-delivery.md.

## Plan (amber)
1. `docs/specs/SPEC-701-…md`: gate, Q3/Q6/Q7/Q8/Q9/Q10/Q12/Q14 answers, AC-1..AC-20 over US-7.1..US-9.4.
2. `closes/delivery_contract.py`: 24 routes (package read/edit/commentary/generate/pages/pdf/xlsx/release, lock, reopen, hand-off read/publish, information returns, vendor read/patch, TIN reveal (organisations' tin.reveal), W-9 requests, TIN match, backup withholding, 1099 batch approve, IRIS CSV, filed, acknowledgement); no transmit route.
3. Mounted in closes.api ROUTERS; make generate.
4. `docs/contracts/closes-delivery.md` and a register row.
5. Rollback: unmount; flags default off.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5506). Ruff and pyright clean; generate clean. TIN last-four is `restricted` (the classification vocabulary has no `pii` level). Gates and tests run once at the S49 end pass (build first, test last).
