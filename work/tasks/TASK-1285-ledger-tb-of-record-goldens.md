---
id: TASK-1285
title: Ledger TB of record and layer engine, finished and footed by goldens (A-02-T07)
spec: SPEC-333
acceptance_criteria: [AC-1, AC-3, AC-4, AC-14, AC-17, AC-18, AC-19]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T07
branch: s9b-ledger-tb
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Golden tests foot Northwind and Granite Peak by exact Decimal, re-adopting creates v2 without
touching v1 or any snapshot, and AJE, RJE and Final answer layer_unavailable while no adjustment
source is registered."

TASK-320 and TASK-322 built most of the row in `ledger/trial_balances.py`: adopt and re-version,
prior-snapshot pairing, the fail-closed `register_adjustment_source` slot, AJE/RJE/Final,
leadsheets, display unit. An audit against the row, SPEC-333 and C9 found these gaps:

1. No golden footing for Northwind or Granite Peak (epic §9 names
   `backend/tests/golden/ledger/tb_layers.yaml`).
2. No integration test that re-adopting writes v2 and leaves v1 and both snapshots untouched.
3. `trial_balance.version_created` is not an outbox event (SPEC-333 AC-4: "Built except the
   event (T07)"; C9 §7). Re-versioning writes an *audit* row of that name instead, while C9 §7
   says adopt and re-version audit `trial_balance.created` and `trial_balance.version_adopted`.
4. Per-layer balance (AC-17, "engine T07"): no `layer_unbalanced` code, and only Unadjusted and
   Final have totals; AJE and RJE have none.
5. Leadsheet rollup from methodology account rules (epic §4.1 row 1, `area_for`): areas come only
   from annotations.
6. `docs/plan/status/status-verified.csv` row A-02-T07 says prior pairing, display unit and the
   leadsheet rollup are missing; TASK-320 built the first two.

## Plan
- **Ledger** (`trial_balances.py`, red):
  - `events.py` (new): `TrialBalanceVersionCreated` (ids and version only), emitted by
    `adopt_trial_balance` (v1) and `adopt_version` (vN) in the caller's unit of work.
  - Audit actions as C9 §7: v1 records `trial_balance.created` and
    `trial_balance.version_adopted`; vN records `trial_balance.version_adopted` (before/after
    version). ED-083 for the misnamed audit row and the missing event.
  - `layer_totals(lines, layer)` for all four layers; `LayerUnbalanced` (409
    `layer_unbalanced`, facts `layer` and `difference`) and `require_balanced`; the view carries
    `layer_balances` for every available layer. The live SPEC-309 view is not made to refuse an
    unbalanced Unadjusted layer (that would hide an imported TB's difference from the tab);
    the C9 view-by-layer route (A-02-T10) calls `require_balanced`.
  - `AreaRule` and `area_of_rules` (the `area_for` rule: first rule in order whose text range
    holds the code); `build_lines` and `trial_balance_view` take `area_rules`, an annotation's
    area wins. Ledger stays dependency-free: rules arrive as arguments; A-02-T10 passes the
    engagement's methodology rules.
  - `api.py` exports the new names. Error-code catalogue regenerated.
- **Goldens**: `backend/tests/golden/ledger/tb_layers.yaml` and
  `test_tb_layers_golden.py`. Northwind PY2025 (seed `_TB_LINES` through the scenario
  document's regions, BOY from the Harborline 1/1/2025 column): Unadjusted footing (six funds,
  investments, net assets; debits = credits 17,663,450.00), the Investments leadsheet with Δ%
  half-even, and the Final layer with AJE-1 (48,600.00 = 33,540.00 + 15,060.00; net assets
  16,861,000.00). Granite Peak FY2026 (blueprint §9.8 with A-02 §5.3's accounts) against FY2025
  (addendum §9.4.1): total assets 26,410,000 / 23,200,000, Δ 3,210,000 and 13.8 %, debits =
  credits 71,910,000. Every figure read as YAML text and compared as `Decimal`.
- **Integration** (`backend/tests/integration/test_tb_versions.py`): adopt v1 through
  `ledger.api` in a unit of work, re-adopt a newer snapshot as v2; v1's row and both snapshots
  (and their lines) are byte-identical before and after, the outbox holds
  `trial_balance.version_created` for v1 and v2, the audit rows are C9's, the view reads v2 and
  still reads v1 on request, and AJE, RJE and Final answer `layer_unavailable` with no source.
- **Unit**: `tests/unit/ledger/test_trial_balances.py` extended (layer totals, rules, the
  refusals before any database work).
- **Docs**: C9 §6/§7 confirmed; status-verified row; decision DEC-394 (golden sources and the
  Granite Peak equity note).
- No migration, no matrix, flag or registry change, no generated file.

## Rollback
Revert the commit: the event has no consumer yet (P-04 stale detection reads the digest), the new
code paths are additive, and the audit action rename only affects new rows.

## Progress log
- 2026-10-26: plan written.
- 2026-10-26: built. Goldens (`tests/golden/ledger`, 12 cases across the two TBs) pass; the
  Northwind golden exposed ED-084 (an adjustment-only account had no BOY against a prior year),
  fixed in `apply_entries`, which also takes the area rules now. ED-083 for the audit names and the
  missing outbox event. `tests/integration/test_tb_versions.py` passes (v1 row and three snapshots
  with their lines keep their `xmin` and content; two outbox events; C9's audit rows; v1 and v2
  views; `layer_unavailable` for AJE, RJE and Final with the slot empty). Unit tests 11. Gates:
  ruff format/check, pyright, lint-imports, banned_patterns, error_codes (`--write`: one new code,
  `layer_unbalanced`), validate_docs, scope_guards, fresh_mfa. DEC-394. Left for A-02-T10: pass
  the engagement's methodology rules as `AreaRule`s and call `require_balanced` in the
  view-by-layer route.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-394 | Golden sources, audit and outbox names, layer balance, area rules | No |
