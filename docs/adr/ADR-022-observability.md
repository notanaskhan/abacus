---
id: ADR-022
title: OpenTelemetry, Sentry and self-hosted LLM tracing
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Busy-season outages are unacceptable, and agent behaviour must be inspectable. Model traces contain client financial data.

## Decision
Backend and frontend emit OpenTelemetry traces, metrics and structured logs, with a trace ID propagated across API, workers and model calls. Errors go to Sentry with data scrubbing enabled. Model traces go to a self-hosted LLM tracing tool inside our AWS account. Logs never contain client financial data or PII.

## Options considered
### OTel + Sentry + self-hosted LLM tracing — chosen
- Pros: Standards-based; client data stays in our boundary
- Cons: Self-hosting effort
- Chosen.

### Hosted LLM tracing SaaS
- Pros: No hosting
- Cons: Client data leaves our boundary
- Rejected.

## Consequences
**Positive**
- End-to-end visibility from click to model call

**Negative / costs accepted**
- One more service to host

## Enforcement
- Logging helper redacts known sensitive fields; lint rule bans raw `print` and unstructured logging
- Sentry scrubbing configured and tested
- Every AI gateway call emits a trace span (ADR-019)

## Guidance for agents
Log structured events through the logging helper.

**Do**
```python
log.info('ledger.pull.completed', entity_id=str(e), rows=n)
```

**Don't**
```python
print(f'pulled ledger for {client_name}: {rows}')
```

## Revisit when
Volume or cost makes self-hosting impractical.

## Related
- ADR-019
- ADR-021
