---
name: temporal-workflow
description: How to write Temporal workflows and activities safely — determinism, versioning, signals, child workflows, tests. Use for any workflow or engagement agent code.
---

# Temporal workflow pattern

**Reference:** `docs/architecture/reference/temporal-workflow.md` (worked examples: the `retrieval` and `screening` workflows).

## Determinism (ADR-017)
Workflows only orchestrate. **All I/O happens in activities**: database, HTTP, files, model calls, clocks, randomness. Use `workflow.now()` and `workflow.random()` inside workflows, never `datetime.now()` or `random`.

## Versioning (ADR-090)
Any change to workflow logic that could alter running histories goes behind `workflow.patched("<change-id>")`. Never edit a running path in place.

## Long-running agents (ADR-062)
Events arrive as signals. Timers schedule work. Periodically continue-as-new with carried-forward state. Specialists are child workflows. State is rebuildable from Postgres (ADR-095).

## Payloads
Encrypted by the payload codec (ADR-017). Pass IDs, not large data: frozen dataclasses of strings in `workflow_types.py`.

## Activities
- Prove the context from the run row first (`load_system_context` / `load_agent_context`); the workflow input is never proof.
- Errors cross as `ApplicationError` carrying the class name only. Decided outcomes are non-retryable; outages are retryable.
- End every failure, cancellation included, in a `fail_run` activity with unlimited retries, so a run never stays `running`.
- Register in the module's `WORKFLOWS` (a map from workflow to its work class: `{RetrievalWorkflow: "interactive"}`, then `register_work_classes(WORKFLOWS)`) and `ACTIVITIES` (and `SUBSCRIPTIONS` for outbox-triggered starts); the worker composes them.
- Start workflows only with `kernel.dispatch.dispatch(Workflow, input, id=..., ...)`: it picks the class's queue (ADR-071). Never call `start_workflow` or pass `task_queue=` (DISPATCH-001).
- Workflow ids name the thing (`retrieval:<run_id>`, `screening:<tenant>:<version>`); choose the reuse and conflict policies deliberately.

## Durable timers and the hold check (the withdrawal purge, P-06-T19; ADR-162 §7)
Copy `EvidenceWithdrawalPurge` (`evidence/workflows.py`, activity body `evidence/withdrawals.py: erase_withdrawn`) for anything that waits days and then erases or lets go of evidence.
- **The timer only wakes; the activity judges.** The workflow sleeps with `workflow.sleep(timedelta(seconds=wait))`, then calls one activity that answers an int: 0 when done, else the seconds to wait next. The activity reads the business clock (`kernel.clock.now`, the demo clock locally, P-37), so a timer that fires early or late never erases early. The database checks again in the same transaction (`evidence_key_destroy` compares `abacus_now()` with `erase_after` and answers `not_due`).
- **Ask the hold check first, fail closed.** Call `kernel.holds.held_versions(tenant, version_ids)` before any erase. It raises `HoldCheckMissing` when nothing is registered: treat that as held (`block_reason = no_hold_check`) and erase nothing. A held version is recorded (`erase_blocked_at`, `block_reason = legal_hold`, audit `evidence_withdrawal.erase_blocked`) and retried a day later. Evidence registers the one check (`holds_covering`) when `evidence/holds.py` is imported; the kernel only holds the slot (ADR-101).
- **Decide again under the lock.** A hold placed between the check and the erase must still win: the erase is a SECURITY DEFINER function that locks the row, re-reads the holds and answers `held`, `not_due`, `destroyed` or `gone`. Only the purge's system actor may call it (migration 0144).
- **Retry until it is done.** The erase activity's `RetryPolicy` has `maximum_attempts=0` (no limit), 5 s doubling to 10 minutes, so an outage delays an erase and never drops it.
- **Keep the history short.** After `PURGE_ATTEMPTS_PER_RUN` (30) activity calls the workflow calls `workflow.continue_as_new` with the attempts so far, so a hold that lasts years never grows one history.
- **Start once.** `on_withdrawn` (an outbox subscription) dispatches with `id=withdrawal:<tenant>:<version>`, `WorkflowIDReusePolicy.REJECT_DUPLICATE` and `WorkflowIDConflictPolicy.USE_EXISTING`, and suppresses `WorkflowAlreadyStartedError`: a redelivered event attaches to the running purge. The flag gates the route only; a started purge always runs.
- **Tests:** `tests/workflows/test_withdrawal_purge_replay.py` replays `withdrawal-purge-v1-blocked-then-erased.json` (recorded by `abacus_tools.workflows.record_withdrawal_purge`); `tests/integration/backfill/test_p06t19_withdrawal.py` proves nothing erases before 30 days, a hold blocks and retries daily, and a missing hold check erases nothing. Runbook: `docs/runbooks/RB-32-withdrawal-erase-and-hold-conflicts.md`.
- **Moving work into an activity needs no patch** when the workflow's commands do not change: P-4's draft-only change (DEC-220) lives in the tick's activity, so `EngagementAgent`'s recorded histories replay unchanged. Anything that changes what the workflow schedules still goes behind `workflow.patched`.

## One frozen draw (the sampler, A-03-T10; ADR-340)
Copy `SampleDrawWorkflow` (`sampling/draw_workflow.py`, activity `sample_draw.run` in `sampling/draw.py`) for work that must produce one immutable result or none.
- The person's start inserts the row as `drawing` and dispatches. The activity re-checks its preconditions (the ties), computes with frozen code, and writes every item in one transaction before marking the row a draft. After the retries a failure marks it `failed` with its code, never a partial list.
- The randomness is a recorded input: the seed is drawn at the start (server `secrets`), stored on the row and passed in. The workflow never calls a random source, so a replay and a re-performance (RB-46 §A) see the same seed.
- Histories `sample-draw-v1-drafted.json` and `sample-draw-v1-failed.json`; a change lands behind `workflow.patched`.

## Operator-started workflows (the OCR backfill, P-11-T25; RB-43 §12)
- An operator command starts the workflow (`abacus_tools.<name>`), never a request: a fixed id per
  tenant (`ocr_backfill:<tenant>`), `ALLOW_DUPLICATE` reuse and `USE_EXISTING` conflict policy, so a
  second start joins the first.
- It pages by cursor (ids only in the payload), runs the same idempotent activities as the live
  path behind the same gates, and never changes the records it reads.
- On staging or production it runs as an ECS one-off task, never from a laptop against a shared
  database.

## Agent runs and sessions (runtime v2, P-10; P-10-T55)
- **`AgentRunWorkflow`** (`agents/run_workflow.py`): one run, its plan, steps, questions, decisions
  and control signals. Started only through `kernel.dispatch` with id `agent_run:<tenant>:<run>`; the
  workflow reads identifiers from signals and everything else through activities
  (`run_activities.py`). Part 2 (questions, approvals) sits behind
  `workflow.patched("agent-run-v2-part-2")`: copy that for any change to what it schedules.
- **Waits** are durable: a plan awaiting approval or a question awaiting an answer is a
  `workflow.wait_condition` on a signal, never a poll; the default answer is applied only by an
  explicit Skip (never by time).
- **`ApprovedWriteWorkflow`** runs a person's approved write under their grant; **child runs**
  started from a session turn are started by an activity through `kernel.dispatch` so they outlive
  the session's workflow.
- **`WorkbenchSessionWorkflow`** (`workbench/session_workflow.py`): one turn at a time from a side
  queue, idle end after an hour, continue-as-new carrying the queue and the open question.
- Histories: `agent-run-v1-*.json`, `agent-run-v2-*.json`, `approved-write-v1-*.json`,
  `session-v1-*.json`; replay tests `tests/workflows/test_p10t29_agent_run_replay.py`,
  `test_p10t32_agent_run_replay.py`. A new behaviour adds a `v<N+1>` history.

## One run per object, steps by name (AttachmentTriage, N-01-T12; N-01-T30)
`AttachmentTriage` (`communications/triage_workflow.py`) is the pattern for a per-object pipeline
across modules: one workflow id per object (`attachment_triage:<tenant>:<id>`, so a restart
resumes rather than duplicates), activities called by name so communications never imports
evidence's internals, identifiers only in the history, and a failing step never undoes the ones
before it. New steps land behind `workflow.patched(...)` (the classify step, N-01-T17). Starting it
is an outbox subscriber on the domain event (`inbox_attachment.received`), never a direct call.

## Tests
- Replay test with recorded histories (required check). Record with `python -m abacus_tools.workflows.record_<name>`; never overwrite a history, add `v<N+1>`.
- Tracing comes from the shared client's interceptor (`kernel.temporal`); don't add your own.
- Time-skipping environment for multi-day or multi-week behaviour (ADR-077)
