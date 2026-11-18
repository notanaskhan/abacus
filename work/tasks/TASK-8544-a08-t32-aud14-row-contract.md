---
id: TASK-8544
title: "A-08-T32: AUD-14 log row v1.1: address check, confirmed total, difference"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
branch: a08-t32-aud14-contract
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: A-08-T32
---

## Objective
Contract first for the AUD-14 live swap: the confirmation log row carries the Address, Confirmed and Difference columns the artboards draw.

## Plan (green)
1. confirmations_contract_models.py: RowAddressCheckOut (method, verified_by_name, verified_on) and ConfirmationRowOut.address_check, confirmed_total, difference (default null; v1 readers unaffected)
2. confirmations_service.py: the log query reads the newest address verification and the response's confirmed total; difference = book total less confirmed (code)
3. docs/contracts/confirmations.md v1.1; make generate

## Progress log
- `2026-11-18` — Built 2026-11-18 (S49 open rows, round 2). Per-line confirmed amounts are not stored (the response keeps a total), so lines stay book-only; the log's Item column is the type's label (screen copy). Gates and tests run once at the S49 open-rows end pass (build first, test last).
