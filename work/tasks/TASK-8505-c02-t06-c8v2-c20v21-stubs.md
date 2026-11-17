---
id: TASK-8505
title: "C-02-T06: C8 v2 and C20 v2.1 contract stubs: CLS-07 posting, CLS-11 console, POR-16 write grant"
spec: SPEC-700
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
branch: c02-t06-c8v2-c20v21-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T06
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.3. Pydantic models and 501 routes behind adjustments.posting and closes.gl_console, one matrix action each, make generate, docs/contracts/adjustments.md v2 and c20-integrations.md v2.1 with seed examples (batch 2026-08-A, QBO 48213-48218).

## Plan (red)
1. `adjustments/posting_contract.py`: 14 routes (close view with tallies, approve, request approval, undo, withdraw, reject-close, record external, xlsx export, dry run, post with Idempotency-Key, batch undo, retry, ask-client, redate); client 404, flag 404, human-only 403, then 501.
2. `integrations/w1_contract.py`: console, posting log + CSV, activity, batch drawer, firm switch enable/disable, GL-posting settings, engagement ledger settings; portal write grant / revoke (firm principals 404).
3. Mounted in adjustments.api and integrations.api ROUTERS; `make generate`.
4. Contracts: C8 v2 and C20 v2.1 sections with operations, status words, human-only actions, audit events, Copperleaf examples; register rows record both frozen Fri Sep 15, 2028.
5. Rollback: unmount the routers; flags default off.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5505). Ruff and pyright clean on the new files; make generate clean. The plan's 'one stub per screen family' maps to two routers (posting in adjustments, console and grants in integrations): CLS-11's console and POR-16's grant share C20. Gates and tests run once at the S49 end pass (build first, test last).
