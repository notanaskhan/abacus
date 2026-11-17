---
id: TASK-8533
title: "C-01-T37: CLS-04 Accounts states a, a2, b, d, e, f and composed c-prime"
spec: SPEC-655
acceptance_criteria: [AC-35, AC-36, AC-37, AC-38]
risk_zone: green
status: in-review
branch: c01-t37-cls04
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T37
---

## Objective
CLS-04 Accounts: account tree with rollups and contra parentheses, filter, Detail and Workpaper segmented, register, arrangement drawer, schedule tables with tie marks, off-n pill to CLS-06, policy citation to SHL-08, Open in Excel, category change to SHL-10, bank and card leaves to CLS-05. AC: the tree foots (539,055.45 = 163,543.05 + 375,512.40), no Post AJE control renders, b2 and c stay absent until C-02.

## Plan (green)
1. fixtures/seed/close-accounts.ts: Copperleaf August tree (verbatim), Prepaid Insurance workpaper per state, register; handlers/closes.ts serves them (accounts no longer 501)
2. fixtures/scenarios/CLS-04.ts: a, a2, b, cprime, d, e, f as Raj Malhotra
3. screens/CLS-04: copy, index (CLS04 on closeAccountsOptions, closeWorkpaperOptions, closeRegisterOptions, closeSummaryOptions), scenarios re-export, CLS-04.test.tsx
4. routes/firm/closes.tsx: the Accounts tab body; bank leaves navigate to /closes/$closeId/accounts/$accountRef

## Progress log
- `2026-11-17` — Built; CLS-04 vitest 16 pass, tsc and eslint clean. c-prime figures: recording AJE-02 lowers Prepaid to 2,800.00 and Other Current Asset to 49,124.95 (the spec), and so Asset to 538,355.45, Net Income to 197,020.00 and Equity to 374,812.40, which still foot. Prior periods' GL cells show their ending balance with the tie mark (the workpaper contract carries one GL balance, the current period's). Link-contract rule 5 fails on earlier stack contracts (CLS-07/11/13, TXP-03/04): fix at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
