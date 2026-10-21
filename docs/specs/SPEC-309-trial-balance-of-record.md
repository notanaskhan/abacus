---
id: SPEC-309
title: "The trial balance of record, first slice: adopt and re-version a ledger snapshot, prior-year pairing, code-computed balance and leadsheets, areas and WP refs"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-050, ADR-005, ADR-140]
related_specs: [SPEC-028, SPEC-308]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This is the first slice of A-02 (AUD-06), with A-03's leadsheet rollup.

- An audit engagement adopts one of its entity's immutable ledger snapshots as its trial balance of record, for a label (Standard, Interim, Prior, Budget or Preliminary) and a period.
- It can pair the snapshot with an earlier snapshot for the beginning-of-year column.
- A newer snapshot becomes the next version, with a reason. Nothing earlier changes.
- The ledger computes every figure, total, the balance check, the leadsheets and Δ%. The browser never sums.
- `ledger` stays dependency-free; `assurance` authorises and hosts the routes.

Migration 0073 adds:
- `trial_balances` (only `current_version_no` is updatable);
- `trial_balance_versions` (insert-only, with a CHECK that the actor is human);
- `trial_balance_annotations` (insert-only; the newest row per account counts).

## 2. Acceptance criteria
- **AC-1 Adopt.**
  - `POST /v1/engagements/{id}/trial-balances` takes a snapshot, an optional prior snapshot, a label and a display unit, and writes version 1 in one unit of work.
  - A snapshot of another entity gives `snapshot_entity_mismatch`.
  - A second trial balance for the same work item, entity, label and period end gives 409 `trial_balance_exists`.
  - An engagement without an assurance item gives 409 `no_assurance_item`.
  - The agent is denied `trial_balance.adopt`.
- **AC-2 Read.**
  - `GET …/{tb}?version=` returns each account with BOY (the prior's net), debit, credit, EOY net (debit minus credit), change, area and WP ref.
  - It returns totals and the balance, and every version with who adopted it and from which source.
  - Accounts that appear in only one year are kept.
- **AC-4 Layers.**
  - Only `unadjusted` exists. AJE, RJE and Final answer 409 `layer_unavailable` until an adjustment source registers (A-06); the slot fails closed.
  - The trial balance is balanced exactly when debits equal credits. Otherwise the view carries the difference.
- **AC-5 Leadsheets.**
  - `GET …/{tb}/leadsheets` returns one leadsheet per audit area (alphabetical, Unassigned last), showing PY, CY, Δ and Δ%.
  - Δ% is computed against the magnitude of PY and rounded half-even to 0.1; it is none when PY is 0.
  - No account is dropped.
- **AC-6 Annotations.**
  - `POST …/{tb}/annotations` sets the area and WP ref of up to 500 accounts, with an optional reason.
  - Unchanged accounts write nothing. Amounts are never editable.
- **AC-7 Re-version.**
  - `GET …/{tb}/candidates` lists the entity's snapshots, each with the code-computed number of lines changed and the net change against the current version.
  - `POST …/{tb}/versions` takes a snapshot, a reason and `seen_version`. A stale `seen_version` gives 409 `tb_version_stale`; the same snapshot gives 409 `tb_same_snapshot`; a different period is refused.
- **AC-8 Web.** A "Trial balance" engagement tab has:
  - the empty state, to adopt with a prior and a label;
  - a header with the label pill, period, version, Balanced or Off pill, and the provenance caption;
  - the newer-version banner, with "Use vN…" and a required reason;
  - an Accounts table with selection, "Set area and WP ref", and server totals;
  - Leadsheets;
  - the version list.

## 3. Out of scope (later slices)
- Tie-out checks (A-02-T11, T17).
- Line agreement and ticks (P-04 field ticks).
- TB sign-off through the review module.
- Open in Excel.
- Live ledger connections and POR-16.
- Mapping and grouping sets (A-03-T06, T08).
- Working-paper cells linked to the trial balance (`tb_linked`).
