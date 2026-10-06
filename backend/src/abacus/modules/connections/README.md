# connections

Connections to clients' systems, sync runs, and the retrieval pipeline (ADR-037, ADR-038, ADR-040). Owns `connections` and `sync_runs` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `Connector` (ABC) is the one contract (ADR-037):
  - `capabilities`, `authorise_url`, `exchange_code`, `refresh`, `pull`, `changes_since`, `fetch_attachment`, `health`;
  - read-only (CONN-001: no network imports, no write-shaped methods, no public methods beyond the contract);
  - `pull` returns `RawPayload` (the provider's bytes unaltered, what was read, `next_cursor`).
- `CONNECTORS` maps a provider to its factory. `FakeConnector` serves JSON from `fake_connector_dir` (local and test only), written by `abacus_tools.synthetic.connector_fixtures`. `parse_trial_balance` is the fake format's strict parser.
- `start_retrieval(ctx, *, engagement_id, request_item_id, period) -> run_id`:
  - authorises the human for `evidence.upload`, checks the item is the engagement's and open or received, and finds the entity's active connection;
  - records `sync_run.started`;
  - idempotent: a running or succeeded run for the same item and period is returned instead (`sync_run.requested_again`).
- `load_system_context(tenant_id, run_id) -> SystemContext` proves the context from the run row (it must be running). Workers call it first in every activity.
- Stages: `pull_raw`, `normalise_raw`, `validate_run`, `snapshot`, `render`:
  - each takes only the system context, authorises its own action, and is idempotent with no duplicate audit events;
  - `run_pipeline` runs them in order;
  - `fail_run` ends a running run;
  - `is_retryable` classifies errors for the workflow;
  - `RunFailed(status, code)` ends a run.

## Temporal (TASK-010b)
- `RetrievalWorkflow` (`workflows.py`, name `retrieval`):
  - runs the activities `retrieval.pull_raw`, `normalise_raw`, `validate_run`, `snapshot`, `render` in order, each with up to 6 attempts;
  - on a non-retryable failure, or once retries are exhausted, runs `retrieval.fail_run` and returns `RetrievalOutcome(status, code, evidence_version_id)`;
  - its input is `RetrievalInput(tenant_id, run_id)`, strings only.
- **Activities** (`activities.py`) prove their context from the run row first. Decided outcomes are non-retryable `ApplicationError`s whose type is the exception's class name (`RunFailed` carries status and code). A retry after success returns quietly.
- **Names and history:** activity names are fixed. A change to the workflow needs `workflow.patched(...)`, and `tests/workflows/histories/retrieval-v1.json` must still replay (AC-19).
- **Starting runs:** `trigger_retrieval` (API) records the run, then starts the workflow. The ID is `retrieval:<item>:<start>_<end>`; it reuses a running workflow and only allows reuse after failure. If Temporal is unreachable the run is ended as `workflow_unavailable` (503).
- **Routes:**
  - `POST /v1/engagements/{id}/retrievals` (`evidence.upload`) → 202 with the run;
  - `GET …/retrievals/{sync_run_id}` (`request_item.read`).
- **Worker:** `python -m abacus.worker` checks the key service, payload codec and evidence bucket at boot. Locally it needs the same `fake_connector_dir` as the API.
- **Payloads** are encrypted by `kernel.crypto.payload_codec` (ADR-017). WF-001 and an import contract keep workflows free of I/O.

## Rules
- **The system context** acts on its run's engagement only (`authorise` checks it) and is issued only here (SYS-001), from the run row.
- **The raw bytes never leave `pull_raw`;** every other stage re-reads stored data.
- **Validation failure** marks the run `failed_validation` and stops: no snapshot, no evidence (AC-11).
- **Sync runs are the pull log** (ADR-040). The database keeps them forward-only, with write-once results. Composite keys tie connection, engagement, snapshot and evidence to one client entity, and `succeeded` requires all of them.
- **Dependencies:** identity, engagements, organisations, ledger, evidence and requests (BOUND-002).
