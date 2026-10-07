# Reference: connector contract, fake connector and pipeline stages

The pattern every connector and retrieval copies (SPEC-000 §22), from `backend/src/abacus/modules/connections/` (TASK-010/010a/010b). Binding rules: ADR-037, ADR-038, ADR-040, ADR-004, ADR-017, ADR-052, ADR-101. Workflow side: `temporal-workflow.md`.

## The contract

```python
# modules/connections/connector.py
class Connector(ABC):
    provider: ClassVar[str]
    def capabilities(self) -> Capabilities: ...              # datasets, oauth, incremental, attachments
    async def authorise_url(self, state: str, redirect_uri: str) -> str: ...
    async def exchange_code(self, code: str, redirect_uri: str) -> None: ...
    async def refresh(self) -> None: ...
    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload: ...
    async def changes_since(self, since: datetime) -> Sequence[str]: ...
    async def fetch_attachment(self, ref: str) -> RawPayload: ...
    async def health(self) -> bool: ...
```

- **Capabilities, not provider names:** callers read `capabilities()`; an operation a connector doesn't declare raises `NotSupported`. Never branch on `connection.provider` (ADR-037).
- **`RawPayload`** is the provider's response unaltered: `content` bytes, `media_type`, `source`, `pulled_at`, `request` (what was read, for the access log) and `next_cursor` (None: complete). A connector never parses, trims or re-encodes.
- **Errors:** `ConnectorError(code)` carries a short snake-case code recorded on the sync run; anything that isn't a safe code becomes `provider_error`, so provider text never travels. `Unavailable` (`retryable = True`) is a temporary outage; everything else is a decided failure.
- **Read-only (ADR-040, CONN-001):** the contract has no write operations. `CONN-001` rejects write-shaped method names (`create`, `update`, `delete`, `write`, `post`, `put`, `patch`, `upload`, `send`) in `modules/connections/`, and the conformance suite checks it again at run time.
- Connectors are registered by provider name in `service.CONNECTORS` (`{"fake": _fake}`); `connector_for(connection)` raises `ConnectorError("unknown_provider")` otherwise.

## The fake connector

```python
# modules/connections/fake.py
class FakeConnector(Connector):
    provider: ClassVar[str] = "fake"
    async def pull(self, dataset, period, cursor) -> RawPayload:
        path = fixture_path(self._directory, self._connection_id, dataset, period)
        content = await asyncio.to_thread(path.read_bytes)     # missing -> ConnectorError("no_data")
        if _is_fault(content): raise Unavailable("provider_unavailable")
        return RawPayload(content, MEDIA_TYPE, SOURCE, datetime.now(UTC), request)
```

- Local runs and tests only (`fake_connector_dir`, refused elsewhere by settings). It serves `<fake_connector_dir>/<connection_id>/trial_balance-<start>_<end>.json` byte for byte.
- A file holding `{"fault": "unavailable"}` simulates an outage (retryable); a missing file is `no_data`; malformed bytes are served as is, because rejecting them is the normaliser's job.
- Fixture format (provider-shaped JSON, written by `abacus_tools/synthetic/connector_fixtures.py`): `dataset`, `entity.name`, `period.{start,end}`, `currency`, `lines[{id, code, name, debit, credit}]`, `control_totals.{debit,credit}`. Amounts are decimal strings, never floats. Product code can't import the generator (ADR-101), so the directory is the hand-over.
- Helpers: `write_trial_balance(dir, connection_id, tb, period_start=…, entity_name=…, control_totals=…)` (override the totals to simulate a provider mismatch), `write_fault`, `write_raw` (arbitrary bytes).
- Local: `make seed` (`abacus_tools/local/seed_dev.py`, local and test only, idempotent) connects every client entity without an active connection to a fake one and writes a balanced synthetic trial balance for each engagement's fiscal period, so *Retrieve trial balance* works. Rerun it after creating an engagement. The worker and API must share the same `fake_connector_dir`.

## The pipeline (ADR-038)

```
start_retrieval ─▶ sync_run(running) ─▶ pull_raw ─▶ normalise_raw ─▶ validate_run ─▶ snapshot ─▶ render
  (API, human)                          raw bytes   parse into the   control totals  immutable    evidence version
                                        write-once  ledger model     checked         ledger        + fulfilment by rule
                                                                                     snapshot      + run succeeded
```

- **`start_retrieval`** (`service.py`) authorises the human (`evidence.upload`) inside the unit of work, checks the item is `open` or `received` and the client entity has an active connection, and records the run (`sync_run.started`). While a run for the same item and period is running or has succeeded, triggering again returns it (`created=False`; a unique index settles races). The workflow is started afterwards (`temporal-workflow.md`).
- **Each stage takes only the `SystemContext`** that `load_system_context` proved from the run row; it touches only that run and engagement. Each authorises its own action (`connection.pull`, `evidence.upload`), re-reads what it needs, and returns identifiers: **the raw bytes never leave `pull_raw`**.
- **1-2 `pull_raw`:** calls the connector, stores the bytes write-once via `stage_content` (fingerprint, version ID), records them on the run. Pulls at most once per run: a recorded payload is returned. `Unavailable` is re-raised for the workflow to retry; any other `ConnectorError` ends the run with its code.
- **3 `normalise_raw`:** `fake_format.parse_trial_balance` treats the payload as hostile (AGENTS.md #8): size cap, strict UTF-8, no duplicate keys, amounts only as plain decimal strings, control and format characters refused. Errors are a `NormaliseError(code)`; the run fails `unprocessable` or with that code.
- **4 `validate_run`:** `ledger.validate` (`modules/ledger/normalise.py`) returns a stable failure code or None: `empty`, `period_mismatch`, `unsupported_currency`, `duplicate_account`, `duplicate_source_ref`, `control_totals_mismatch`, `unbalanced`, `zero_total`. A failure ends the run `failed_validation`: no snapshot, no evidence (AC-11). Code computes, models judge (ADR-050): all arithmetic is `Decimal` in code.
- **5 `snapshot`:** re-normalises, re-validates, and `ledger.record_snapshot` inserts an immutable snapshot (ADR-004), linked to the run (`sync_run.snapshot_linked`). `record_snapshot` refuses anything unvalidated (`Unvalidated`).
- **6 `render`:** renders the snapshot as a workbook (`evidence.render_trial_balance`), `evidence.add_version` stores it with provenance (source, `retrieved`, pulled-at, period, snapshot) under the idempotency key `snapshot:<snapshot_id>:item:<request_item_id>`, `requests.fulfil_by_rule` links it to the item (`rule`, not `human`; `open → received`), and the run finishes `succeeded` (`sync_run.succeeded`). A person still decides acceptance (ADR-005).
- **Across modules:** only `api.py` imports (`ledger.api`, `evidence.api`, `requests.api`, `engagements.api`, `identity.api`, `organisations.api`); the dependency list is enforced by BOUND-002.

## Idempotency, failure and the pull log

- **Every stage is safe to repeat** (Temporal may retry or deliver twice). A repeat finds its work done (`raw_fingerprint`, `snapshot_id`, `evidence_version_id` already set) and returns the recorded result with no new audit event. Writes lock the run row (`lock_run`), re-check inside the unit of work, and keep the first writer's result.
- **Forward-only:** `running` → `succeeded`, `failed` or `failed_validation`. A finished run refuses more work (`RunFailed`); `fail_run` marks only a run that is still `running`, and a finished run is never reopened. Retrying means a new run.
- **`sync_runs` is the pull log** (ADR-040): connection, engagement, item, dataset, period, status, failure code, raw fingerprint and size, source, pulled-at, snapshot, evidence version, who started it, when. Results are write-once, composite keys tie connection, engagement, snapshot and evidence to one client entity, and `succeeded` requires all of them. Every transition is audited (`sync_run.*`).
- **Failure codes** are short snake-case codes, never provider text: connector codes (`no_data`, `provider_unavailable`), `connection_inactive`, `unprocessable`, normaliser and validation codes, and the workflow's `provider_unavailable`, `internal_error`, `cancelled`, `workflow_unavailable`.

## The conformance suite

- `backend/tests/unit/connections/conformance.py` (the `connector.py` docstring says `tests/connectors/`; `make check` collects only `tests/unit`). Every connector supplies a `HarnessFactory` (scratch directory → `Harness(connector, responses)`) and parametrises one test over `conformance_params({"name": factory})`, as `test_fake_conformance.py` does.
- It checks that the class is concrete with a `provider`; capabilities are declared; every declared dataset pulls byte for byte with typed `RawPayload` fields and a non-empty `request`; pulls are deterministic and `pulled_at` is the time of the pull; an undeclared dataset, OAuth methods (when `oauth` is false), `changes_since` and `fetch_attachment` raise `NotSupported`; `health()` is a bool; no method is write-shaped.
- A new connector is not done until it is in that parametrisation.

## What a real connector adds

- **Authorisation (ADR-037):** `oauth=True`, `authorise_url` and `exchange_code` with `state` checked on the callback, and `refresh`. Tokens are Restricted (ADR-031): stored encrypted, never logged, never in a workflow payload. Connection rows (`status`, `scopes`, `expires_at`) must reflect expiry and revocation, so `pull_raw` ends the run `connection_inactive` rather than failing mid-pull.
- **Read-only enforcement (ADR-040):** a client exposing only reads (provider read POSTs explicitly allowlisted), the narrowest read scopes the provider offers, a worker egress allowlist of approved provider hosts, and an integration test that intercepts traffic and fails on any non-read request. Today only the CONN-001 name check and the conformance check exist; no egress allowlist or traffic-intercepting test yet.
- **A format module per provider** like `fake_format.py`: strict, hostile-content parsing into the common ledger model, with the same short error codes.
- **Pagination and incremental pulls** via `cursor`, `next_cursor`, `changes_since`; `pull_raw` currently pulls once with no cursor, so a multi-page provider needs a stage that stores each page's raw payload.
- **More datasets and checks:** extend `Dataset` and the ADR-038 validations (opening balance plus activity equals closing, GL detail reconciles to the trial balance, all periods present); today only the trial balance and its control totals exist.
- **Errors:** map provider failures to safe codes; `Unavailable` only for retryable ones, with rate limits and backoff.
- **Access log:** each pull's `request` string is recorded for the client-visible log; the client-facing view is not built yet.
- Register the factory in `CONNECTORS`, pass the conformance suite, and add a provider reference beside this one (ADR-037 follow-up).

## Not yet
- Any real provider, OAuth, a connections UI, scheduled or incremental retrieval, and GL detail.
- Egress allowlist and the traffic-intercepting read-only test (ADR-040).
