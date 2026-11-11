---
id: TASK-6812
title: "T-05-T13: Fixture-mode scenarios for all 57 artboards from the contract stubs: screens/TXP-xx/scenarios.ts, fixtures/handlers/tax-entity.ts, and a ScriptedRunSource for TXP-00 B"
spec: SPEC-651
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s36-t05-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-05-T13
---

## Objective
Every artboard renders in fixture mode at its own clock with no network call.

## Plan (amber: written before the build)
1. `fixtures/seed/tax-entity.ts`: Ridgeline 2025 Form 1065 on the generated workbook v1 types:
   TXP-02's 28 accounts (Run 1's snapshot leaves 1300 unmapped), TXP-06's two ownership periods,
   TXP-00's runs and ten tasks, the clocks, personas, figures, and Run 3's ScriptedRunSource script
   (7 of 10, three running).
2. `fixtures/handlers/tax-entity.ts`: trial balance (account and line views), partners and runs
   by snapshot; writes 501 like the stubs.
3. `fixtures/scenarios/TXP-{00,01,02,05,06,07,10,11}.ts` and `screens/TXP-xx/scenarios.ts`: one
   scenario per contract artboard (57), persona, clock and snapshot from the contract's table.
4. Test: `fixtures/seed/tax-entity.scenarios.test.ts` (every contract artboard has a scenario,
   57 in all, clocks and personas, reads with no network, writes 501, the scripted run).

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- The TXP screens themselves are later T-05 rows; this row gives them their scenarios.
- Artboard-specific payloads beyond the shared reads (memo sections, Schedule K lines, capital
  rows, issues, sheet cells) join each screen's scenario with its FE row; Harborview's waterfall
  (TXP-06 b, d) serves Ridgeline's reads until E5 part 2 adds its structure.
- TXP-00 c's clock is Jun 2 at 9:00 AM CT (the contract gives the date only).
