# ledger

Ledger snapshots and trial balance lines in the common ledger model (ADR-038). Owns `ledger_snapshots` and `trial_balance_lines` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `NormalisedTrialBalance` and `LedgerLine` are the common ledger model that provider parsers produce (`connections/fake_format.py` for the fake provider). `NormaliseError(code)` is the parsers' failure.
- `validate(tb, *, period_start, period_end) -> str | None` returns a failure code or `None`. Checks run in a fixed order: `empty`, `period_mismatch`, `unsupported_currency`, `duplicate_account` (NFKC and case-folded codes), `duplicate_source_ref`, `control_totals_mismatch`, `unbalanced`, `zero_total`.
- `record_snapshot(tx, *, client_entity_id, period_start, period_end, tb, raw_fingerprint, pulled_at, source) -> SnapshotRef`:
  - runs inside the caller's unit of work and re-validates against the requested period first (`Unvalidated`);
  - the same pull gives the same snapshot (`created=False`, nothing recorded);
  - audit event: `ledger_snapshot.created`.
- `snapshot_view(tenant, snapshot_id) -> SnapshotView` is ledger's own read model. Callers map it, for example to the renderer's input.

## Rules
- **Snapshots and lines are immutable:** insert-only for the app, and a trigger rejects UPDATE, DELETE and TRUNCATE for every role (ADR-004). A snapshot exists only if debits equal credits (database CHECK).
- **Dependencies:** ledger depends on no other module. Evidence and connections may depend on ledger.
- **Lines** can only be inserted in the transaction that created their snapshot (trigger).
- **Not yet in SPEC-000:** the opening + activity = closing check and the GL-to-TB reconciliation (ADR-038). They wait until GL datasets exist.

## General ledger detail (SPEC-034; TASK-069)
- **Model and checks (`general_ledger.py`, pure):** `GlEntry`, `GlSummary` (per account opening, debits, credits; months; totals), `validate_gl(summary, tb_accounts, period)` in a fixed order: `period_mismatch` (lines outside the year, or a month with no lines when income accounts have balances), `unbalanced`, `missing_account`, `extra_account` (a non-zero account the trial balance lacks), `roll_forward` (opening + debits - credits = trial balance closing, to the cent). Openings: the export's own; else, when the export prints none, derived for balance sheet accounts (numbered 1-3) and flagged `opening_derived`; else zero. Up to five accounts with differences, or the missing months, come back as details.
- **Snapshots (`gl_service.py`):** `record_gl_snapshot` re-checks inside the caller's unit of work against a trial balance snapshot, then inserts `gl_snapshots`, `gl_account_balances` and `gl_entries` (batches of 5,000) in that one transaction; the entries must add up to the summary. The same file gives the same snapshot. `year_end_trial_balance`, `gl_snapshot_view`, `gl_entries` (pages) read them back.
- **Immutable** like trial balance snapshots: insert-only grants, the `ledger_immutable` triggers, and balances and entries insertable only in their snapshot's transaction (`gl_rows_with_snapshot`). A GL snapshot's balances CHECK that each account rolls forward.

## Trial balance of record and layers (SPEC-309, SPEC-311, SPEC-333; TASK-320, TASK-322, TASK-1285)
- **Adopt and re-version (`trial_balances.py`):** `adopt_trial_balance` writes `trial_balances` and version 1 (audits `trial_balance.created` and `trial_balance.version_adopted`); `adopt_version` adds the next version with a reason (audits `trial_balance.version_adopted`). Both emit the outbox `trial_balance.version_created` (`events.py`). Versions are insert-only; nothing earlier is touched (ADR-004).
- **Layers:** Unadjusted always; AJE, RJE and Final only once an adjustment source registers (`register_adjustment_source`, filled by fieldwork), `layer_unavailable` before. `layer_totals` gives each layer's debits and credits; `require_balanced` refuses `layer_unbalanced` with the difference.
- **Areas and leadsheets:** an annotation's area wins, else the caller's `AreaRule`s (the methodology's `area_for` rule, passed in); `leadsheets` rolls lines up by area with Unassigned last, Δ% half-even to 0.1. Goldens: `tests/golden/ledger/tb_layers.yaml`.
