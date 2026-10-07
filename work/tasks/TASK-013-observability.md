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

### Interface contract — TASK-013 (tests written independently — ADR-078)
**Imports:**
- `abacus.kernel.telemetry`: `configure_tracing`, `tracer`, `current_trace_id`, `current_span_id`, `current_traceparent`, `continue_trace`, `TRACEPARENT`.
- `abacus.kernel.logging`: `get_logger`.
- `abacus.kernel.error_tracking`: `configure_error_tracking`, `scrub`, `report`, `ReportingInterceptor`.
- `abacus.kernel.uow.relay`: `OutboxEvent` (new optional `trace_context`), `relay_once`.
- `abacus.kernel.config`: `Settings` (`log_level`, `otlp_endpoint`, `sentry_dsn`, `release`).

**Telemetry:**
- `configure_tracing(service, exporter=None)`:
  - sets the global tracer provider once (resource: service name, `deployment.environment`, and version when `release` is set);
  - a later call with an exporter adds it to the existing provider;
  - exports over OTLP only when `otlp_endpoint` is set.
- `current_trace_id()` returns 32 hex digits inside a recording span, else None; `current_span_id()` returns 16.
- `current_traceparent()` returns a W3C traceparent matching `TRACEPARENT`, or None.
- `continue_trace(tp)`: inside it, new spans belong to `tp`'s trace (children of that span). None or a malformed value is a no-op.

**One trace (integration, with local Temporal and an in-memory exporter):**
- Under one parent span, `start_retrieval` plus starting the `retrieval` workflow, through a client with `TracingInterceptor` and its worker, gives the workflow spans (`StartWorkflow`/`RunWorkflow:retrieval`) and every activity's `StartActivity`/`RunActivity` spans the parent's trace ID.
- Every `audit_events` row written in that flow has `trace_id` equal to that trace ID.
- The `outbox` row for `evidence_version.created` has a `trace_context` whose trace ID is the same.
- Relaying that event (`relay_once` with the screening subscription) starts the screening workflow in the same trace. Its activities, `ai.call` and the screening audit rows carry the same trace ID.
- Outside any span, `trace_id` and `trace_context` are NULL.
- The database enforces formats: `audit_events.trace_id ~ ^[0-9a-f]{32}$`, `outbox.trace_context` a traceparent. The app may insert `outbox.trace_context`; the relay reads it.
- The recorded workflow histories still replay.

**API:** each request produces one server span named by route template (e.g. `GET /v1/engagements/{engagement_id}/request-items`), with no request or response bodies and no headers as attributes. `/v1/me` with a bearer token: the `Authorization` value appears in no span attribute.

**Gateway:**
- `call()` produces exactly one `ai.call` span with attributes `ai.prompt`, `ai.tier`, `ai.agent_id`, `ai.purpose`, `ai.status`, `ai.attempts`, `ai.cost_usd` (string), `ai.model` and `ai.inputs_hash`;
- one `ai.attempt` event per attempt, with `outcome`, `input_tokens`, `output_tokens` and `cost_usd`, including `budget_refused` and `provider_error`;
- no attribute or event contains the prompt text, rendered context or model output.

**Logging:**
- Each line has `trace_id`/`span_id` inside a span and omits them outside one.
- An exception field (`error=exc`) is written as its class name only.
- `log_level`: None means debug in local/test and info elsewhere; a set level filters lower levels.
- Stdlib library logs at WARNING and up are written as `{"event":"library.log","logger":<name>,"level":…}` with no message text; logs below WARNING are dropped.
- Existing refusals (Restricted, unclassified, arbitrary objects) are unchanged.

**LOG-001** (`banned_patterns`), under `src/abacus/` except `kernel/logging.py`, flags:
- `import logging`, `from logging …`, `import structlog`, `from structlog …`;
- a log method call (`.debug/.info/.warning/.error`) whose keyword value is `str(e)`, `repr(e)` or an f-string containing `e`, where `e` is bound by `except … as e` in the file.

`str(x)` of other names is allowed.

**Error tracking:**
- `configure_error_tracking(service)` returns False and does nothing without `sentry_dsn`. With a DSN it initialises Sentry: PII off, no local variables, no source context, no breadcrumbs, no default or auto integrations, `before_send=scrub`. Idempotent.
- `scrub(event)` returns a new event containing only:
  - `event_id`, `timestamp`, `level`, `platform`, `environment`, `release`, `sdk`;
  - `exception.values[]` as `{type, value=type, module?, stacktrace.frames[{module, function, lineno, in_app, filename, abs_path}]}`;
  - `contexts.trace{trace_id, span_id}`;
  - `tags` restricted to `route`, `tenant_id`, `error_type`, `activity`.
- Hostile inputs leave no trace in the output: messages, `vars`/`pre_context`/`context_line` in frames, `request` (URL, headers incl. Authorization, cookies, data, query), `user`, `extra`, `breadcrumbs`, other contexts and other tags.
- `report(exc, **tags)` is a no-op when unconfigured. Otherwise it captures with only the allowlisted tags.
- **`ReportingInterceptor`** (worker): an activity raising a retryable `ApplicationError` is reported with `error_type` = its `type` and `activity` = its activity type; a non-retryable one is not reported; any other exception is reported. The exception is always re-raised unchanged.
- **API:** an unhandled route error returns the fixed 500 body, logs `api.unexpected_error` with the class name, and calls `report` with the route template.

**Contract revision 1 (after the security and architecture reviews; supersedes earlier bullets where they differ)**
- **Scrubbing exporter.** `configure_tracing(service, exporter)` wraps every exporter (OTLP and test) in `ScrubbingExporter` (`telemetry.scrubbed(span)`). Exported spans have:
  - only the attributes `http.route`, `http.request.method`, `http.method`, `http.status_code`, `http.response.status_code`, `temporalWorkflowID`, `temporalRunID`, `temporalActivityID`, `temporalActivityType` and `temporalUpdateID`, plus any key starting `ai.`, `outbox.` or `tenant.`;
  - no `exception` events;
  - other events keeping only `outcome`, `input_tokens`, `output_tokens` and `cost_usd`;
  - error status descriptions cut to the class name before any `:` (or `"error"` if that isn't a class name).

  A hostile exception message or URL, query, client address or user agent never reaches an exporter.
- **Test exporter.** Tests use `telemetry.test_exporter()`, one in-memory exporter per process attached once behind the scrubber; clear it per test. It is refused outside local/test.
- **Gateway span.** `ai.call` no longer carries `ai.purpose` or `ai.inputs_hash`. On an exception its status is ERROR with the class name, and it records no exception event.
- **Relay span.** `outbox.publish` records no exception event.
- **API.** Inbound `traceparent`/`tracestate` request headers are ignored: a request with a chosen traceparent gets a different trace ID, and its audit rows don't carry the caller's. A lifespan shutdown calls `shutdown_tracing()` and `flush_errors()`.
- **OTLP.** Outside local/test the endpoint must be `https://` (otherwise `RuntimeError` at `configure_tracing`). A trailing slash is normalised; the exporter URL is `<endpoint>/v1/traces`. The sampler is `ParentBased(ALWAYS_ON)`.
- **Sentry:**
  - `scrub` also keeps `server_name` (the service); frames no longer keep `abs_path`.
  - `report` sets `contexts.trace` from the current OpenTelemetry trace and span IDs.
  - `init` also passes `enable_metrics=False`, `enable_logs=False`, `auto_session_tracking=False` and `send_client_reports=False`.
  - `flush_errors()` flushes when configured.
  - `ReportingInterceptor` doesn't report `temporalio.exceptions.CancelledError`, and reports a retryable failure only when `activity.info().attempt == 1`.
- **Logging:**
  - Configuration is lazy (on the first emitted line, not on `get_logger`). `configure_logging(level=None, *, force=False)` sets it explicitly; `force=True` reconfigures.
  - The library handler is added to the root logger only once, and existing handlers stay.
  - Root is raised to WARNING if lower.
  - `uvicorn.access` is disabled, and `uvicorn`/`uvicorn.error` have no own handlers and propagate.
- **LOG-001:**
  - It checks calls on receivers named `_log`, `log` or `logger` (bare or as an attribute).
  - The event (positional argument 0) must be a string literal.
  - Inside an `except … as e` block, a keyword field that mentions `e` in any form other than the bare name, `type(e)` or `type(e).__name__` is flagged.
  - Also flagged: `__import__("logging"|"structlog")` and `importlib.import_module(...)` of those.
  - The same names outside that `except` block are not flagged.

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
| opentelemetry-sdk, opentelemetry-instrumentation-fastapi, opentelemetry-exporter-otlp | >=1.45.1 / >=0.66b1 (locked) | tracing (ADR-022); allowlisted. The exporter brings grpcio, protobuf and requests transitively (stage-3 audit) | founder (Q5) |
| sentry-sdk | >=2.71.0 (locked) | error tracking (ADR-022); allowlisted | founder (Q5) |

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

- `2026-10-07` — Implemented telemetry, logging, LOG-001, the audit and outbox trace context (migration 0011), the Temporal `TracingInterceptor` (stable; the plugin is experimental), API instrumentation, the gateway span, the relay span, Sentry with allowlist scrubbing and the worker reporting interceptor.
  - Smoke test: one trace ID covers the request, the retrieval workflow and its 5 activities, all 9 audit rows and the outbox `trace_context`.
  - The reference doc and the observability skill are written.
  - Contract written.
- `2026-10-07` — Reviews fixed (contract revision 1).
  - Security blockers: exception text on spans, and URL/query/IP/user agent on API spans. Fixed with a scrubbing exporter over every exporter, plus inbound trace headers ignored.
  - Independent tests: about 168 test functions, 3,800 cases. They found 2 API bugs, both fixed:
    - the inbound traceparent was not ignored, because the middleware ran after the instrumentation;
    - the route was lost from error reports, because the middleware copied the scope.

    The fix strips the headers at the app entry, editing the scope in place.
  - Results: 6,999 unit tests pass; the TASK-013 integration and replay tests (94) pass.
  - Pending: PR #14's CI fixes (the relay engine in worker fixtures; a pin that predates 011b's billing). Rebuild on main after #14 merges.
## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Implementation, reviews and independent tests are done on `task-013-observability` (based on main before PR #14).
- **Exact next step:** After PR #14 merges, rebuild on main (new branch, cherry-pick), run the full suite with the compose DB stopped (CI-like conditions), open the PR, confirm CI, then founder review.
- **Open issues:** follow-ups for TASK-014:
  - the collector and its auth (`OTEL_EXPORTER_OTLP_HEADERS`);
  - the Sentry DSN and release;
  - whether a DSN and endpoint are mandatory outside local/test;
  - pinning `temporalio` and moving to `OpenTelemetryPlugin` when it is stable;
  - an exporter-only dependency (`opentelemetry-exporter-otlp-proto-http`) to drop grpcio.
