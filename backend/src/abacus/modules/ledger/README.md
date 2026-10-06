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
