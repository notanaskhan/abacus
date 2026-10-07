# Reference: tracing, logging and error tracking

The pattern every module copies (SPEC-000 §15, §22), from the walking skeleton (TASK-013). Binding rules: ADR-022, ADR-031, ADR-007, ADR-019, ADR-090.

## One trace ID end to end

```
API request ─▶ retrieval workflow ─▶ activities ─▶ outbox row ─▶ relay ─▶ screening workflow ─▶ screen ─▶ ai.call
                └──────── one trace ID ─ also on every audit row written along the way ────────┘
```

- **API:** FastAPI instrumentation opens one server span per request, named by route template.
  - Every request starts its own trace: inbound `traceparent`/`tracestate` headers are dropped, so callers can't choose the trace IDs that audit rows record.
  - The scrubbing exporter keeps only route, method and status (never URL, query, client address, user agent, headers or bodies).
  - uvicorn's access log is off; requests are traced instead.
- **Temporal:** the shared client (`kernel.temporal.temporal_client`) carries `temporalio.contrib.opentelemetry.TracingInterceptor`.
  - Starting a workflow puts the caller's trace in its headers, and workers using that client continue it in the workflow and each activity.
  - This is replay-safe: the interceptor adds no workflow commands, and the recorded histories still replay.
- **Outbox:** the unit of work stores the transaction's W3C `traceparent` on each outbox row (`outbox.trace_context`). The relay publishes inside that trace (`outbox.publish` span), so a retrieval and the screening it triggers share one trace.
- **Model calls:** each gateway call is an `ai.call` span with prompt reference, tier, agent, status, attempts, cost and model, plus an `ai.attempt` event per attempt (ADR-019).
  - Prompts, context, output, the purpose text and the inputs hash never go on a span; the hash stays in the usage record.
- **Audit rows:** the unit of work writes the current trace ID into `audit_events.trace_id` (ADR-007), so any audited change leads back to its trace.
- **Export:** `kernel.telemetry.configure_tracing(service)` runs once per process (API, worker).
  - Spans export over OTLP when `ABACUS_OTLP_ENDPOINT` is set (https outside local and test). Exporter authentication comes from the standard `OTEL_EXPORTER_OTLP_HEADERS` environment variable (TASK-014). Otherwise spans stay in process.
  - Tests use `test_exporter()`, one shared in-memory exporter: clear it per test.
  - Spans are flushed at shutdown (`shutdown_tracing`).
- **Scrubbing backstop:** every exporter is wrapped in `ScrubbingExporter`, which covers spans written by libraries (FastAPI, Temporal), not just ours.
  - Only allowlisted attributes leave: the HTTP route, method and status; Temporal's workflow, run, activity and update IDs; and our own `ai.*`, `outbox.*` and `tenant.*` attributes.
  - `exception` events (message and stack trace) are dropped, and error statuses are cut to the exception's class name.
  - Our own spans also opt out of recording exceptions.

```python
from abacus.kernel.telemetry import tracer, current_traceparent, continue_trace

with tracer(__name__).start_as_current_span("ledger.normalise", attributes={"rows": n}):
    ...
```

Span attributes are identifiers, counts and outcomes. Never put client content, amounts, prompts or model text on a span.

## Logs

```python
from abacus.kernel.logging import get_logger

_log = get_logger(__name__)
_log.info("sync_run.started", run_id=run.id, tenant_id=ctx.tenant_id)
_log.warning("outbox.publish_failed", event_id=event.id, error=exc)   # logs "ValueError"
```

- **Format:** one JSON object per line with `event`, `level`, `timestamp`, `trace_id` and `span_id` (inside a span), and the fields.
- **Fields:** scalars, UUIDs, dates, or classified models with no Restricted or untagged field. Anything else raises (ADR-031).
- **Exceptions:** pass the exception itself. Only its class name is logged, because messages can quote client data. LOG-001 rejects `str(exc)`, `repr(exc)` and f-strings with it in log fields, and any stdlib `logging` or direct structlog use in product code.
- **Level:** `ABACUS_LOG_LEVEL`, defaulting to `debug` locally and in tests, `info` elsewhere.
- **Third-party libraries' own logs:** warnings and up appear as `event="library.log"` with the logger name and level only. Library messages can contain SQL parameters or URLs, so they are not kept.
  - The handler is added to the root logger, never replacing others: a test runner's capture still works.
  - Configuration is lazy (first log line), or explicit with `configure_logging(level, force=True)`.
- **Scripts:** CLI tools, seeds and migrations don't configure tracing, so their audit rows have no trace ID.

## Error tracking (Sentry)

- **On/off:** enabled only when `ABACUS_SENTRY_DSN` is set (`kernel.error_tracking.configure_error_tracking`). Unexpected API errors and retryable activity failures are reported. Decided outcomes, such as validation failures, forbidden actions or a failed run, are not reported.
- **Scrubbing by allowlist** (`scrub`): every event is rebuilt from scratch. It keeps:
  - the exception's type and stack frames (module, function, line, file name; no local variables, no source context, no absolute paths);
  - environment, release, the service (`server_name`), and the OpenTelemetry trace and span IDs (set by `report`);
  - the tags `route`, `tenant_id`, `error_type` and `activity`.

  Exception messages are replaced by the type name. Requests, headers, cookies, users, breadcrumbs, extras and every other context are dropped.
- **SDK settings:** automatic integrations are off, and so are PII, local variables, metrics, logs, sessions and client reports.
- **What the worker reports:** retryable activity failures, once per activity (on the first attempt). Cancellations are not reported.
- **Flushing:** queued reports are flushed at shutdown (`flush_errors`).
- **Extending:** to send more, change the allowlist and add a test showing hostile values don't survive.

## Not yet
- Metrics, dashboards, alerts and the canary (ADR-094).
- The self-hosted LLM trace store (ADR-022).
- Browser telemetry (deferred; no TS packages allowlisted).
- A deployed collector (TASK-014).
- Database spans: the SQLAlchemy and asyncpg instrumentation isn't allowlisted.
