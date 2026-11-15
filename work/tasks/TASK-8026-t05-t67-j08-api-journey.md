---
id: TASK-8026
title: "T-05-T67 part 1: API-level J08 journey on the loaded Ridgeline return"
spec: SPEC-651
acceptance_criteria: [AC-11, AC-12, AC-13, AC-14]
risk_zone: green
status: in-review
branch: t05-t67-j08-api-journey
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-05-T67
---

## Objective
`backend/tests/integration/tax/test_j08_entity_return.py`: shoebox to workbook, mapping approval, L3 allocation, off 6,200, fix approval, Run 3, tie, memo stale, K-1 drafts, CCH reconciliation; an agents-off variant with zero model calls and a declined-consent variant.

## Plan
1. [x] Load `tax_board` + `entity` at Sep 14 9:52 AM into the test's own database (the A-04-T28 pattern), and read it back through the services:
   - `entity_blockers`: none of mapping, allocation, tie-out or run;
   - workbook values: 06 line 18a 6,200, M-2 line 9 6,866,200;
   - `reconcile` with no import: no difference;
   - `usage_records` is empty for the tenant (zero model calls).
2. [ ] Declined-consent variant: decline Ridgeline's `ai_disclosure`, start a run, and the model steps wait on `consent_7216` while the code steps run (T-05-T63's DB clause).
3. [ ] K-1 drafts (five packages Draft from sheet 09) and the CCH round trip: export from the approved checkpoint, an import that matches reports 0 differences, and a 1-dollar change raises one `engine_diagnostic`.
4. [ ] T-05-T65's DB clauses: hostile import parsing (T40), the fix flow's checkpoints (T50); the TJE layers' balance (T63).

## Progress log
- `2026-11-15` — Trial balance seeded and mapped (DEC-5019); the gate reads the tax set. `tests/integration/tax` passes on a real database; tax, ledger and synthetic unit tests 36,942 passed; the two mapping DB tests pass.
- `2026-11-15` — Rebuilt on main 17082f4be. Preparer signs L1 (DEC-5017). The slice now loads end to end into a database; the test found and fixed the recorder order, the memo plan time, the checkpoint hash prefix and `work_item_runs`' missing column (all production paths but the recorder). Run 3 in progress at 9:52 is by design. **Fixed 2026-11-15 (DEC-5019):** `trial_balance_missing`, because the slice never puts Ridgeline's trial balance into the ledger (no snapshot, adoption or form-line mapping), so the J08 "shoebox to workbook, mapping approval" step is not seeded.
- `2026-11-14` — Step 1 built. ruff and pyright clean; it runs against Postgres at the end pass, under the test lock. The workbook key shapes (`06!…`, `07!…`) are read loosely, by sheet prefix and value, until the first run pins them.
