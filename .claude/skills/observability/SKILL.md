---
name: observability
description: How to log, trace and report errors without leaking client data — the logging helper, spans, trace IDs, Sentry. Use when adding logs, spans or error handling anywhere in the backend.
---

# Observability pattern

**Reference:** `docs/architecture/reference/observability.md` (from the walking skeleton, TASK-013).

## Rules
- Log only with `from abacus.kernel.logging import get_logger`; never stdlib `logging` or structlog directly (LOG-001). Fields are identifiers, counts, statuses: the helper refuses Restricted and unclassified values (ADR-031).
- Log an exception as the value (`error=exc`): only its class name is written. Never `str(exc)` or an f-string with it (LOG-001) — messages can quote client data.
- Spans: `from abacus.kernel.telemetry import tracer`; attributes are identifiers and outcomes, never prompts, model output, request bodies or amounts. HTTP, Temporal and outbox spans are automatic — don't add your own for those.
- Unexpected errors: `abacus.kernel.error_tracking.report(exc, **allowlisted_tags)`; expected outcomes (validation, forbidden, not found, failed runs) are not errors to report.
- Crossing a process boundary yourself? Carry `current_traceparent()` and resume with `continue_trace(...)` (the outbox and Temporal already do).
- New Sentry data needs an allowlist change in `kernel/error_tracking.scrub`, with a test that hostile values don't survive.

## Platform side (Q-01 close-out note)
- Metrics: `abacus.kernel.metrics` (`meter(__name__)`) drops any attribute key not in `_ATTRIBUTES`. A new attribute is an allowlist change with a test. Never use a firm name, a person, an email or an amount as an attribute; a tenant is its UUID.
- Browser errors reach Sentry only through `POST /v1/telemetry/errors` (Q-01-T48, T50), which rebuilds each event from an allowlist. Never point the SPA at the Sentry ingest directly: CSP `connect-src 'self'` would refuse it, and the tunnel is the scrubbing point.
- Alerts: every alert references an SLO in `docs/ops/slos.md` or is ticket-only (ADR-093), and carries a runbook URL (ADR-098). Operator dashboards never show cross-firm content.
- Edge logs: WAF logs redact `authorization` and `cookie` (`infra/modules/waf`). A new log destination outside `log-archive` needs a sub-processor row if a vendor receives it (`.claude/skills/infra-terraform/SKILL.md`).
- Environments and what each may hold: `docs/ops/environments.md`. Staging and production telemetry carries synthetic data only until R2.
