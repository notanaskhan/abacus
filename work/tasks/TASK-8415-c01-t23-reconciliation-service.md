---
id: TASK-8415
title: "C-01-T23: Reconciliation service"
spec: SPEC-655
acceptance_criteria: [AC-39, AC-40, AC-41, AC-42]
risk_zone: amber
status: in-review
branch: c01-t23-reconciliation-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T23
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 F5. Reconciliation service: compute on run and on ledger_snapshot.recorded; VM with match links and regions; item resolution (carry forward, cleared) as insert-only human decisions; review.register_reviewable('reconciliation') with a content hash so L1 is blocked while items are open and goes stale on change; Propose AJE from an item through adjustments.api.propose_entry with the firm's classification.

## Plan (amber)
1. `closes/reconciliations.py`: `recompute` (a version only when inputs change; open and carried-forward items move to it with `carried_from_item_id`), `on_ledger_snapshot_recorded` (each open close of the entity), `view`, `resolve_item` (insert-only, a person, once), `item_for_draft`, `entry_lines` (code's AJE sides), `propose_from_item` (adjustments `propose_entry`, the item linked), the `reconciliation` reviewable and its facts (`blocked_code = reconciling_items_open` with the count; the version's content hash, so a new version leaves L1 stale).
2. `run_steps.reconcile_statement` delegates to `recompute` (items now carry).
3. CLS-05 routes in `contract_work.py`: the VM, resolve, entry draft (code's cash side), propose entry.
4. Tests: `tests/unit/closes/test_c01t23_reconciliations.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5410). Lint and pyright clean; the app imports. Partial: statement lines and their regions are not in the VM yet (a region needs a verified C4 citation per line, which the extraction does not mint); the 409 names the open-item count, not each item; the entry draft gives the cash side only (the person picks the offset account). Gates and tests run once at the S48 end pass (build first, test last).
