# Reference: Temporal workflow, activities, versioning and replay

The pattern every module copies (SPEC-000 §22), from the retrieval workflow (TASK-010/010b) and the screening workflow (TASK-011/011b). Binding rules: ADR-017, ADR-090, ADR-007, ADR-014, ADR-022, ADR-031. Worked examples: `modules/connections/{workflows,activities,workflow_types,retrievals}.py` and `modules/agents/{workflows,activities,workflow_types,screenings}.py`.

## Shape

```
trigger ─▶ dispatch(Workflow, Input(ids), id=…) ─▶ workflow (orchestration) ─▶ activities (all I/O)
                                                          └── any failure ─▶ <module>.fail_run (retries forever)
```

- One module owns a workflow, its activities and its payload types. Each module's `api.py` exports `WORKFLOWS` (each workflow's work class, registered with `register_work_classes`), `ACTIVITIES` and `SUBSCRIPTIONS`; `abacus/worker/__main__.py` composes them from `MODULES`, so adding a workflow never touches the worker.
- `kernel.dispatch.dispatch` is the only way to start a workflow: it runs on its work class's queue (`<base>-interactive`, `-time-sensitive`, `-background`, `-batch`), each with its own worker pool (ADR-071, SPEC-003). Its activities run on the same queue.
- Workflows and activities have fixed names (`@workflow.defn(name="retrieval")`, `@activity.defn(name="retrieval.pull_raw")`). Starts and `execute_activity` calls use the name strings. Renaming one breaks replay (ADR-090).

## The workflow: orchestration only

```python
# modules/connections/workflows.py
with workflow.unsafe.imports_passed_through():
    from abacus.modules.connections.workflow_types import RetrievalInput, RetrievalOutcome, ...

@workflow.defn(name="retrieval")
class RetrievalWorkflow:
    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        try:
            await workflow.execute_activity("retrieval.pull_raw", input,
                start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY)
            ...
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(input, "failed", CANCELLED)
                raise asyncio.CancelledError from err
            status, code = _failure(err)
            return await _fail(input, status, code)
        except asyncio.CancelledError:
            await _fail(input, "failed", CANCELLED)
            raise
```

- Activities are called by name, in written-out steps. No I/O, clocks, randomness, repositories, services or the Temporal client in a workflow.
- Two rules enforce it (WF-001, ADR-017 and ADR-090):
  - the banned-pattern rule `WF-001` (`abacus_tools/quality/banned_patterns.py`) allows a workflow module to import only Temporal, safe standard-library types and its own `workflow_types`;
  - the import-linter contract "Workflows orchestrate only" in `backend/pyproject.toml` forbids `abacus.kernel` and the module's repository, service, pipeline, activities and routes.
- The workflow turns an activity failure into an outcome from the `ApplicationError` type and details only (`_failure`): a decided failure keeps its status and code, an outage becomes `provider_unavailable`, anything else `internal_error`.
- Workflow modules are protected paths: changing one needs a founder approval file.

## Payloads: identifiers only

```python
@dataclass(frozen=True)
class RetrievalInput:
    tenant_id: str
    run_id: str
```

- Frozen dataclasses of strings (and `None`), so they serialise stably. No ledger values, names, free text or Restricted fields.
- Input is never proof of anything. Every activity re-derives its context from the run row:
  - retrieval: `load_system_context(tenant_id, run_id)` (the run must exist in the tenant and be `running`; engagement and `on_behalf_of` come from the row);
  - screening: `load_agent_context(tenant_id, run_id)`; if the person the agent acts for is no longer active, the run ends `initiator_inactive`.
- Outcomes (`RetrievalOutcome`, `ScreeningOutcome`) carry status, code and identifiers back.

## Activities

```python
def _as_application_error(exc: BaseException, *, retryable: bool) -> ApplicationError:
    name = type(exc).__name__
    return ApplicationError(name, type=name, non_retryable=not retryable)

@activity.defn(name="retrieval.snapshot")
async def snapshot_activity(input: RetrievalInput) -> None:
    await _stage(input, snapshot)       # proves context, runs the stage, maps errors
```

- **Class name only:** the message is the exception's class name, never its text (messages can carry provider text or database values). Retrieval's `RunFailed` also carries `(status, code)` as details, which the codec encrypts.
- **Retryable vs not:** decided outcomes (failed run, missing or forbidden resource, invalid data) are `non_retryable=True`; provider outages (`Unavailable`, `ProviderError`) and infrastructure errors are retried. Retrieval decides with `pipeline.is_retryable`; screening with its `TERMINAL` set.
- **Repeat-safe:** an activity may run twice. A retry that finds the run already ended returns what it recorded (`succeeded_version`, `_recorded`) and writes no new audit events.
- **Heartbeat** for long activities: `screening.screen` wraps its body in `_heartbeating()` (every 10 s, against a 30 s `heartbeat_timeout`), so a timed-out attempt is cancelled before its retry starts and two attempts never spend the run's budget at once.
- **`fail_run`** ends a run that is still `running` and reports its final state; a run that already finished is left alone.

## Timeouts, retries and ending a run

| | retrieval | screening |
|---|---|---|
| activity timeout | 5 min start-to-close | 2 min; `screen` 5 min plus a 30 s heartbeat |
| retry | 2 s, ×2, up to 1 min apart; 6 attempts | same backoff; 4 attempts |
| `fail_run` retry | unlimited (`maximum_attempts=0`), up to 1 min apart | same |
| execution timeout | 6 hours (set at start) | none |

- Every workflow ends in a `fail_run` activity with unlimited retries: a run never stays `running` because of the workflow, whether the cause was a stage failure, exhausted retries or cancellation. Cancellation runs `fail_run` with code `CANCELLED`, then re-raises so the workflow ends cancelled.
- `fail_run` accepts only codes in the module's `FAIL_CODES` (retrieval also `FAIL_STATUSES`); anything else is recorded as `internal_error`.

## Workflow IDs, and starting

| workflow | ID | reuse policy | conflict policy | started by |
|---|---|---|---|---|
| retrieval | `retrieval:<run_id>` | `ALLOW_DUPLICATE` | `USE_EXISTING` | the API (`retrievals.trigger_retrieval`) |
| screening | `screening:<tenant_id>:<evidence_version_id>` | `ALLOW_DUPLICATE_FAILED_ONLY` | `USE_EXISTING` | the outbox relay (`screenings.start_screening`) |

- IDs are bound to the unit of work they serve, so a repeat attaches rather than duplicates. Qualify with the tenant when the key isn't already unique to one firm: Temporal's namespace is shared by every firm.
- Reuse: a retrieval run is final once finished and a new run gets a new ID, so duplicates are harmless. Screening must not run twice for a version, so only a *failed* workflow may be started again.
- **From the API:** record the run in a unit of work first (`start_retrieval`, idempotent), then start the workflow. If the start fails, end only a run this request created (`workflow_unavailable`, 503); someone else's run is left alone.
- **From an event:** the module subscribes a handler in `SUBSCRIPTIONS = {EVENT_TYPE: start_screening}`; the worker's relay delivers each outbox event at least once. Build the input from the event's identifiers only (a malformed event raises, so the relay backs off and parks it) and suppress `WorkflowAlreadyStartedError`: a redelivery for work already started counts as delivered.
- Start through `kernel.temporal.temporal_client()`, never a client built by hand.

## Encryption and tracing

- Every client (API and worker) shares one `DataConverter` (`kernel/temporal.py`): payloads are sealed by `PayloadEncryptionCodec` (`kernel/crypto/payload_codec.py`: AES-256-GCM, a keyring with a current key ID so keys rotate), and `DefaultFailureConverterWithEncodedAttributes` encodes failure messages and stacks. Nothing readable reaches Temporal. A payload not sealed by a known key is refused. The worker fails at boot if the codec isn't usable.
- The client carries `TracingInterceptor`: the caller's trace continues in the workflow and each activity. The worker adds `ReportingInterceptor` (retryable activity failures to error tracking, once per activity). See `observability.md`.

## Versioning and replay (ADR-090)

- Any change to what a workflow does (an activity added, removed or reordered, a changed failure path) is guarded with `workflow.patched("<change-id>")`, keeping the old path until no workflow runs on it. No workflow uses `patched` yet: the current written-out steps are the v1 baseline.
- Recorded histories live in `backend/tests/workflows/histories/`: `retrieval-v1-{succeeded,failed-validation}.json` and `screening-v1-{completed,skipped,provider-unavailable}.json`. `abacus_tools/workflows/histories.py` stores them decoded (plain payloads, identifiers only) and scrubbed of worker host names and build IDs, so they replay offline with no codec.
- `tests/workflows/test_{retrieval,screening}_replay.py` replay every history with `Replayer` (AC-19), and show that swapping, skipping or adding a stage, or changing the failure path, raises `NondeterminismError`.
- **Never overwrite a history.** Record a new version beside the old ones; every version must keep replaying:

```
cd backend && uv run python -m abacus_tools.workflows.record_retrieval tests/workflows/histories v2
cd backend && uv run python -m abacus_tools.workflows.record_screening tests/workflows/histories v2
```

  The recorders start throwaway Postgres, S3 and Temporal containers (Docker), use synthetic data, and refuse to overwrite an existing file (`refuse_overwrite`). Add the new files to the replay tests' parameters.

## Adding a workflow

1. `workflow_types.py`: frozen identifier-only dataclasses, error-type and code constants.
2. `workflows.py`: `@workflow.defn(name=…)`, activities by name, a `fail_run` ending with unlimited retries, cancellation handled.
3. `activities.py`: prove context from the row, class-name-only errors, repeat-safe, an `ACTIVITIES` tuple.
4. A starter module (`retrievals.py`, `screenings.py`): the workflow ID and its policies; for events, a `SUBSCRIPTIONS` entry.
5. Export `WORKFLOWS` (with each workflow's work class), `ACTIVITIES` and `SUBSCRIPTIONS` from `api.py`, and call `register_work_classes(WORKFLOWS)`; add the module to `MODULES` in the worker.
6. Record `v1` histories and add a replay test with "changed sequence fails" cases.

## Not yet
- A `workflow.patched` change (none has been needed).
- Long-lived workflows with signals, timers or human waits (the engagement agent, ADR-062).
- Search attributes, schedules and Temporal-side metrics.
