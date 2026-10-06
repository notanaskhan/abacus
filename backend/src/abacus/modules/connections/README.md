# connections

Connections to clients' systems, sync runs, and the retrieval pipeline (ADR-037, ADR-038, ADR-040). Owns `connections` and `sync_runs` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `Connector` (ABC) is the one contract every connector implements:
  - `capabilities`, `authorise_url`, `exchange_code`, `refresh`, `pull`, `changes_since`, `fetch_attachment`, `health`;
  - read-only (CONN-001);
  - `pull` returns the provider's bytes unaltered.
- `FakeConnector` serves JSON from `fake_connector_dir` (local and test only), written by `abacus_tools.synthetic.connector_fixtures`.
- `start_retrieval(ctx, *, engagement_id, request_item_id, period) -> StartedRun(run_id, system)`:
  - authorises the human for `evidence.upload`, finds the entity's active connection (`NoConnection`), and records the run (`sync_run.started`);
  - returns the `SystemContext` the pipeline runs under.
- The six stages are `extract`, `store_raw`, `normalise_raw`, `validate_run`, `snapshot` and `render`:
  - each takes `(system, run_id)` and is idempotent;
  - `run_pipeline` runs them in order;
  - `RunFailed(status, code)` ends a run.

## Rules
- **Only identifiers cross stages.** Each stage re-reads the stored raw payload, so retries never carry ledger data (TASK-010b runs them as Temporal activities).
- **Validation failure** marks the run `failed_validation` and stops: no snapshot, no evidence (AC-11).
- **Retrieving twice gives one snapshot and one evidence version:**
  - snapshots are unique per pull;
  - the evidence idempotency key is the snapshot plus the item;
  - fulfilments are unique per item and version.
- **Sync runs are the record of every pull** (ADR-040's access log).
