# ledger

Ledger snapshots and trial balance lines in the common ledger model (ADR-038). Owns `ledger_snapshots` and `trial_balance_lines` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `normalise(content: bytes) -> NormalisedTrialBalance` parses a provider trial balance strictly: decimal strings only, control characters refused, limits on size. `NormaliseError(code)` on anything unexpected.
- `validate(tb, *, period_start, period_end) -> str | None` returns a failure code or `None`. Checks run in a fixed order: `empty`, `period_mismatch`, `duplicate_account`, `control_totals_mismatch`, `unbalanced`.
- `record_snapshot(tx, *, client_entity_id, tb, raw_fingerprint, pulled_at, source) -> SnapshotRef`:
  - runs inside the caller's unit of work and re-validates first (`Unvalidated`);
  - the same pull gives the same snapshot (`created=False`, nothing recorded);
  - audit event: `ledger_snapshot.created`.
- `trial_balance_for(tenant, snapshot_id, *, entity_name) -> evidence.api.TrialBalance` is the renderer's input.

## Rules
- **Snapshots and lines are immutable:** insert-only for the app, and a trigger rejects UPDATE, DELETE and TRUNCATE for every role (ADR-004). A snapshot exists only if debits equal credits (database CHECK).
- **Dependencies:** ledger depends on evidence (the renderer's input type), never the reverse.
- **Not yet in SPEC-000:** the opening + activity = closing check and the GL-to-TB reconciliation (ADR-038). They wait until GL datasets exist.
