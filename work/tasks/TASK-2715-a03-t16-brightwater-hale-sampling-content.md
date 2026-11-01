---
id: TASK-2715
title: A-03-T16 Brightwater Hale A-03 content (part one — the populations by inverse construction)
spec: SPEC-580  # A-03 §5.4
acceptance_criteria: [AC-1]
risk_zone: green
status: partial
epic: A-03
plan_key: A-03-T16
branch: s22-a03-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "make seed-demo loads every A-03 scenario through the APIs with no content constant
  in code, and fixture mode and seed-demo render identical figures for every state in section
  5.4." **Not met yet**: this part builds the content; the loader wiring is part two.

## Done (part one)
- `abacus_tools/synthetic/scenarios/brightwater_hale/sampling_content.py`: census v2 (412) and v1
  (409, $182,300.00 short), Granite Peak disbursements (1,912, $38,640,200.00, strata 24 / 1,102 /
  786), Northwind distributions (64), the four scenario seeds, the census workbook; the designed
  participants and SURL payments copied from the A-03-T09 goldens, placed at the recorded
  ordinals (DEC-1659's inverse construction).
- `tests/unit/scenarios/test_a03t16_sampling_content.py`: the real 2.3 draws return AUD-11 a's 25
  in order and AUD-11 f's 24 + 16 = 40 ($3,698,700.00).

## Remaining (part two)
1. A `sampling` slice (opt-in, needs `standards`, `people`, `audit_core`) and loader handlers:
   BH FS groupings v1 through `ledger.api.import_grouping_set` + publish (Margaret Okonkwo);
   BH-EBP-210 Table 2 through the standards import (kind `attribute_sample_sizes`; only the
   designed row is canon: moderate, 10 %, 0 %, 90 % → 25 — other rows need the PF's review).
2. Granite Peak FY2026 TB with 128 accounts footing to A-02 §5.3's lines, its FY2025 prior
   mapping, adopted through `ledger.api`; Granite Peak's GL snapshot of the 1,912 payments.
3. Census v1 and v2 uploads as Dana Kowalski (evidence), the populations and ties through
   `sampling.api`, the draws with the scenario seeds (`draw(..., scenario_seed=)`), Hannah
   Leclerc's approval of Version 2.
4. `make fixtures export` and the fixture-vs-seed-demo equivalence test for every §5.4 state.

## Progress log
- 2026-11-01: part one built and its unit suite run (4 passed). Part two left for the next S22
  pass; row stays partial.
