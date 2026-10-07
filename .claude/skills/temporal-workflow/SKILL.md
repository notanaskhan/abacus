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
- Register in the module's `WORKFLOWS` / `ACTIVITIES` (and `SUBSCRIPTIONS` for outbox-triggered starts); the worker composes them.
- Workflow ids name the thing (`retrieval:<run_id>`, `screening:<tenant>:<version>`); choose the reuse and conflict policies deliberately.

## Tests
- Replay test with recorded histories (required check). Record with `python -m abacus_tools.workflows.record_<name>`; never overwrite a history, add `v<N+1>`.
- Tracing comes from the shared client's interceptor (`kernel.temporal`); don't add your own.
- Time-skipping environment for multi-day or multi-week behaviour (ADR-077)
