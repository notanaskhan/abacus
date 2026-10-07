---
id: TASK-013
title: Tracing, structured logs and error tracking
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-progress
branch: task-013-observability
worktree:
created: 2026-10-06
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
One trace ID from API through workflow, activities and gateway; logging helper that refuses Restricted fields; error tracking with classification-driven scrubbing.

## Scope
In: SPEC-000 §15 — "Trace spans from API through workflow, activities and gateway with one trace ID. Structured logs with no Restricted fields. Error tracking with scrubbing." Also the `observability.md` reference (§22), and AC-20 (the gates).
Out:
- metrics, dashboards, alerts and the canary (ADR-094; TASK-014 or later);
- the self-hosted LLM tracing tool (ADR-022; later);
- browser tracing (Q3);
- a deployed collector (TASK-014).

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-022, ADR-031, ADR-094 (scope only), ADR-007 (audit trace ID), ADR-017/ADR-090 (Temporal), ADR-019 (gateway spans)

## Plan
- [x] Plan approved by human (founder, 2026-10-07: all recommendations, Q1–Q6)

### Design (for founder review)
Amber. It touches protected paths: `abacus.api`, the worker, the kernel uow/relay, `ai_gateway`, `pyproject.toml` and `uv.lock`, and possibly a migration.

**1. One trace from the API to the model call (ADR-022, §15).**
- **Packages:** `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi` and `opentelemetry-exporter-otlp` (all allowlisted). They are set up once in `kernel/telemetry.py` (`configure_tracing(service)`), and the API and worker call it at start.
- **API:** FastAPI instrumentation gives one server span per request.
  - The route template is recorded, never the URL or query (paths carry IDs only).
  - Request and response bodies and headers are never recorded.
- **Temporal:** `temporalio.contrib.opentelemetry.TracingInterceptor` (it ships with `temporalio`; no new package) goes on the client (API and relay) and the worker. The workflow and each activity then join the trace that started them. It is replay-safe (ADR-090).
- **Gateway:** `call()` opens an `ai.call` span per attempt (ADR-019). Its attributes are prompt ref, model, tier, outcome, inputs hash, tokens and cost, never prompt or output text.
- **Outbox:** the relay opens one span per publish.
- **Export:** OTLP when `otlp_endpoint` is set. Locally and in tests nothing is exported unless configured, and tests use the SDK's in-memory exporter. TASK-014 runs the collector.
- **Audit:** the unit of work writes the current trace ID into `audit_events.trace_id` (the ADR-007 column exists but is never filled). Every audit row can then be followed to its trace.

**2. One trace across the outbox (Q1).** Retrieval ends in `evidence_version.created`, and screening starts from the relay in another process.
- Recommend: record the W3C `traceparent` with each outbox row, through a new nullable column `outbox.trace_context`. Its value is identifiers only, safe for the relay role to read.
- The relay continues that trace when it starts the screening workflow. A retrieval and its screening then share one trace ID end to end: API → retrieval workflow → activities → outbox → screening workflow → `screen` → `ai.call`.

**3. Structured logs.**
- **Trace IDs:** the existing helper (`kernel/logging.py`) adds `trace_id`/`span_id` from the current span to every line. It already refuses Restricted and untagged values (ADR-031); the existing tests cover that.
- **Errors:**
  - `log.error(event, error=exc)` accepts an exception and logs only its class name; messages can carry data.
  - Passing `str(exc)` anywhere is flagged by a new rule.
- **Level:** a `log_level` setting.
- **New rule LOG-001** (ADR-022 "bans unstructured logging"): outside `kernel/logging.py`, no `import logging` or `logging.getLogger`, and no structlog use except through the helper. `print` is already banned (ruff T20).
- **SDK logs:** the stdlib loggers of third-party libraries (uvicorn, temporal, otel) are routed through the same JSON renderer at WARNING and above.

**4. Error tracking (Sentry; ADR-022, ADR-031).** `sentry-sdk` (allowlisted) is enabled only when `sentry_dsn` (SecretStr, restricted) is set. Recommend (Q4) scrubbing by allowlist, not by denylist, so nothing classified can slip through:
- **Kept:**
  - the exception type and its stack frames (module, function, line, no local variables);
  - environment, release, trace ID, route template, and tenant ID as a tag (internal).
- **Dropped:**
  - exception messages (replaced by the class name);
  - request bodies, headers, cookies, query strings and URLs;
  - local variables (`include_local_variables=False`), breadcrumbs from logging, user and IP (`send_default_pii=False`);
  - any extra or context data not on the allowlist.
- **Classification:** when an event carries a Pydantic model (e.g. via `set_context`), `sensitive_paths` decides, and a model with any Restricted or untagged field is dropped whole.
- **Tests:** a `before_send` unit test with hostile events (a message with a cell value, a request with an Authorization header, locals holding a trial balance) proves nothing survives.

**5. Docs.** `docs/architecture/reference/observability.md` (§22) covers spans, the logging helper, error tracking, and what never goes in any of them. The matching skill is updated.

**6. Tests.**
- **Unit:** the logging helper (trace IDs, the error field), the Sentry scrubber, LOG-001.
- **Integration with local Temporal and the in-memory exporter:**
  - one API retrieval request produces spans for the request, the retrieval workflow and its activities, sharing one trace ID;
  - with Q1, the screening workflow, `screen` and `ai.call` join the same trace;
  - the audit rows carry it.
- **Replay:** the existing retrieval and screening histories must still replay with the tracing interceptor installed (it adds no workflow commands).

### Questions for approval
- **Q1. One trace across the outbox:** add a nullable `outbox.trace_context` column (migration `0011`), so retrieval and screening share one trace (recommended), or let screening start a new trace that links to the retrieval's?
- **Q2. Local trace viewing:**
  - recommended: no collector locally (export only when `otlp_endpoint` is set; tests use the in-memory exporter);
  - or allowlist a Jaeger/collector image for `docker-compose.yml`.
- **Q3. Browser tracing and Sentry:** ADR-022 says the frontend emits traces too, but SPEC-000 §15 names only the API, workflows, activities and gateway, and no TypeScript OTel or Sentry packages are allowlisted. Recommend deferring browser telemetry to a later task, so the SPA propagates no `traceparent` yet.
- **Q4. Sentry scrubbing:** an allowlist (keep only exception type, frames, environment, release, trace ID and route; drop everything else, recommended), or the SDK's default scrubbing plus classification-driven denylists?
- **Q5. Dependencies:**
  - Add the allowlisted `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp` and `sentry-sdk`.
  - No SQLAlchemy, asyncpg or httpx instrumentation (not allowlisted); database spans are left out for now.
- **Q6. Approval file paths:**
  - `backend/pyproject.toml`, `backend/uv.lock`;
  - `backend/src/abacus/api/**`, `backend/src/abacus/worker/**`;
  - `backend/src/abacus/kernel/uow/**` (trace ID in audit rows and outbox);
  - `backend/src/abacus/ai_gateway/**`;
  - `backend/migrations/**` (Q1), `backend/src/abacus_tools/quality/schema_check.py` (outbox columns);
  - `backend/src/abacus_tools/quality/banned_patterns.py` and its test (LOG-001);
  - `.claude/skills/**` (the observability skill).

### Steps
1. Approval file. Telemetry kernel, the logging helper's trace IDs and error field, LOG-001.
2. API and worker tracing, the Temporal interceptor, gateway and relay spans, the audit trace ID, and the outbox trace context (Q1).
3. The Sentry setup and scrubber.
4. The contract, independent tests, two reviews, `make check`, then the PR.
5. The `observability.md` reference and the skill.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-07` — Plan drafted (§1–6, Q1–Q6) for founder review while PR #14 (TASK-012) runs CI.
- `2026-10-07` — Approved with all recommendations:
  - Q1: an `outbox.trace_context` column (migration 0011);
  - Q2: no local collector;
  - Q3: browser telemetry deferred;
  - Q4: Sentry scrubbing by allowlist;
  - Q5: the four allowlisted packages;
  - Q6: the approval file was written at the founder's instruction.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Approved; approval file written. Step 1 in progress.
- **Exact next step:** On approval, write `work/approvals/TASK-013.yaml` with the Q6 paths, then step 1. Rebase onto main once PR #14 merges.
