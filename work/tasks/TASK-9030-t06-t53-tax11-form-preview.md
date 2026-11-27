---
id: TASK-9030
title: "T-06-T53: TAX-11 form preview a-e on T17"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-t06-t53-tax11
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T53
---

## Objective
TAX-11 a-e in fixture mode on T17: thumbnails with diagnostic counts, page with typed values tracing to SHL-09/SHL-08, K-1 list, diagnostics to TXP-10, Approve return… to SHL-12 disabled with reasons, Export to TAX-09, Download draft in the overflow menu, loading skeleton.

## Done
- Approve stays disabled with 'n blocking diagnostics' until state d
- No control on the screen transmits or files
- Diagnostics in code's words (title, page_key additive)
- Fixture from the Python scenario (scenario.tax11-preview.json)

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6035. Backend adds diagnostic title and page_key (pure test in test_t06t50). T17 kit extended additively (packages/ui 1582 green). 8 TAX-11 tests green. Fixture hit a record-handler order clash: the entity handlers' record 404s for the tax-returns id, so the scenario puts the tax-returns record last. BOUND-001 caught a tools import of tax internals; rules are now exported through tax.api.
