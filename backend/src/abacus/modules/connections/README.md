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
  - runs `retrieval.pull_raw`, `normalise_raw`, `validate_run`, `snapshot`, `render` (5-minute timeout each, up to 6 attempts);
  - any failure, cancellation included, ends in `retrieval.fail_run`, which retries until it succeeds, so a run never stays `running` because of the workflow;
  - returns `RetrievalOutcome(status, code, evidence_version_id)`;
  - input `RetrievalInput(tenant_id, run_id)`.
- **Activities** (`activities.py`) prove their context from the run row first. Every error crosses to Temporal as an `ApplicationError` whose message and type are the exception's class name only, never its text; decided outcomes are non-retryable. A retry after success returns the recorded result.
- **Encryption:** payloads are sealed by `kernel.crypto.payload_codec` (a keyring, so keys can rotate), and failure messages and stack traces are encoded too (`kernel.temporal`). Outside local and test the client uses TLS and an API key.
- **One workflow per run** (`retrieval:<run_id>`, 6-hour execution timeout), work class `interactive` (`dispatch` runs it on `<base>-interactive`, SPEC-003). Behind `patched("work-slots")` it first holds a work slot (`retrieval.acquire_slot`): while it waits, the run stays `running` with `queued_reason` and `estimated_start_at` (audited `sync_run.queued` / `sync_run.resumed` on change), the API reports `queued`, and past the class's maximum wait it fails `capacity_timeout`. The slot is released at the end (`retrieval.release_slot`) and renewed by every stage. `trigger_retrieval` records the run, then starts its workflow, attaching if it's already running. If the start fails, a run this request created is ended as `workflow_unavailable` (503); someone else's run is left alone.
- **Routes:**
  - `POST /v1/engagements/{id}/retrievals` (`evidence.upload`) → 202, or 409 (`no_connection`, `item_not_open`, `engagement_archived`) or 503;
  - `GET …/retrievals/{sync_run_id}` (`request_item.read`) with status (`queued` while waiting for a work slot), code, evidence, `started_at`, `finished_at`, `queued_reason` and `estimated_start_at` (set when queued and when the reason changes; rounded to whole minutes).
- **Worker:** `python -m abacus.worker [--classes ...]` checks the database (application and relay roles), key service, payload codec and evidence bucket at boot. It runs one pool per work class served (each registering every module's `WORKFLOWS`/`ACTIVITIES`); the process serving `interactive` also runs the outbox relay (modules' `SUBSCRIPTIONS`, TASK-011b) and, for one release, the legacy queue. Any pool or the relay stopping stops the process; on SIGTERM every pool drains together. Locally it needs the same `fake_connector_dir` as the API.
- **Replay (AC-19):** `tests/workflows/histories/retrieval-v<N>-*.json` are recorded with `python -m abacus_tools.workflows.record_retrieval`, decoded and scrubbed.
  - Never overwrite one: a changed workflow uses `workflow.patched(...)` and adds `v<N+1>`.
  - Every version must keep replaying.
- **Static rules:** WF-001 and an import contract keep workflows free of I/O and of anything outside the sandbox.

## Rules
- **The system context** acts on its run's engagement only (`authorise` checks it) and is issued only here (SYS-001), from the run row.
- **The raw bytes never leave `pull_raw`;** every other stage re-reads stored data.
- **Validation failure** marks the run `failed_validation` and stops: no snapshot, no evidence (AC-11).
- **Sync runs are the pull log** (ADR-040). The database keeps them forward-only, with write-once results. Composite keys tie connection, engagement, snapshot and evidence to one client entity, and `succeeded` requires all of them.
- **Dependencies:** identity, engagements, organisations, ledger, evidence and requests (BOUND-002).

## The connection flow (SPEC-020; TASK-036)
`connect.py`; routes under `/v1/engagements/{id}/connection` plus `POST /v1/connections/complete`.

**Connecting:**
- A client admin starts a flow (`connection.create`, fresh MFA). The state is kept only as its SHA-256 in `connection_states`, bound to that user, the engagement and its client entity, for 10 minutes.
- The provider redirects to the SPA (`/client/connect/callback`), which completes the flow with the same person's token (D1), so no route is unauthenticated.
- The state is spent in its own unit of work whatever happens, and a reused, expired or someone else's state is refused (`invalid_state`).
- The contract's `exchange_code` returns opaque `Credentials`, sealed with the tenant's key into `connection_secrets` (`seal`, with the connection's ID as associated data).
- Connecting again revokes the entity's live connection. A partial unique index allows one live connection (`active` or `needs_attention`) per entity.

**After connecting:**
- **Check** (`connection.check`): `refresh` then `health`. A failure sets `needs_attention`, which also stops pulls, because `pull_raw` needs `active`.
- **Revoke** (`connection.revoke`): deletes the secret; a running retrieval then fails `connection_inactive`.
- **Notifications:** `ConnectionCreated` and `ConnectionRevoked` notify the engagement's partner and managers.
- **Access log** (`connection.read_log`): the engagement's sync runs, newest first, 50 a page.
- **Providers:** `fake` ("Demo ledger") only where `fake_connector_dir` is set. Its demo sign-in returns `code=demo` and a fixed credential.
