---
id: TASK-3272
title: A-05-T34 Northwind EBP scenario slice 2 (investments, Form 5500, distributions; Granite Peak documents)
spec: SPEC-000  # row (SPEC-640 AC-34)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T34
branch: s27-a05-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Net assets foot to 16,812,400 + 48,600 = 16,861,000 across the EBP-06, EBP-07 and EBP-08
goldens, and every document is synthetic with fictional providers."

## Plan (amber)
- `abacus_tools/synthetic/scenarios/brightwater_hale/ebp2.py`: the figure book (five funds
  14,800,000, BrokerWindow 19 accounts 1,700,000, loans 312,400 = 16,812,400; balances for 301
  participants foot to it; + receivable 48,600 = 16,861,000), 64 distributions with the sample
  10 by seed 0x7B13C4, and the documents (certified trust report with page 4 certification,
  BrokerWindow detail, loan report, balances, distributions register, 408(b)(2) disclosures, two
  invoices, ERISA budget statement, Summit testing report, draft Form 5500, Granite Peak's
  estimates, masters and four board minutes).
- Loader: slice `ebp2` (needs `ebp`) uploads them through `evidence.api` as Dana Kowalski
  (Northwind) and Luis Ferrante (Granite Peak).
- Golden `tests/golden/ebp/northwind_py2025_slice2.yaml`; test
  `tests/unit/synthetic/test_a05t34_ebp_slice2.py`.
- Not here: the Form 5500 draft's Sep 21 upload is an event on the demo clock only once A-05's
  Form 5500 service lands (it uploads with the slice today).

## Progress log
- 2026-11-04: built; the figure book foots by code.

## Decisions made during this task
DEC-2252.
