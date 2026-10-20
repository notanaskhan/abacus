---
id: ADR-154
title: Observability and on-call vendors - CloudWatch, X-Ray, Sentry and Better Stack
status: proposed
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Accept by 2026-11-13.** ADR-022 names OpenTelemetry and Sentry but no on-call or status vendors, and the sub-processor register needs every vendor that sees data. This ADR is P-67, drafted under Q-01-T10 and built under Q-01-T25, T41 and T51. The plan's backlog table has no recommendation text; the decision below is ch. 06 D-OPS-14, §3.5, §3.6 and §6.9. Vendor costs are out of scope here.

## Decision
- **Stack.** CloudWatch (logs, metrics, alarms) and X-Ray through ADOT, Sentry (US, scrubbed), and Better Stack for status page, uptime and on-call. Client data stays in the Accrued AWS account.
- **On-call tool** is Better Stack on-call or PagerDuty, not Opsgenie (end of life announced; verify).
- **Status page** is firm-facing only at `status.<product-domain>`; the portal never links to it.
- **Sub-processor register** is `docs/operations/sub-processors.yaml` (protected), with role, data seen, region, DPA status and needed-by. A check fails when an egress host in Terraform has no register row.
- **Better Stack sees no client data** (synthetic checks and alert metadata only).

## Options considered
### Option A: CloudWatch + ADOT + Sentry + Better Stack — chosen
- Pros: client data stays in AWS; one vendor for paging and status.
- Cons: Better Stack region and DPA still to verify.

### Option B: PagerDuty for paging
- Pros: established.
- Cons: a second vendor beside the status page.
- Why rejected: one vendor is simpler; PagerDuty remains the named alternative.

## Consequences
**Positive**
- Every data-seeing vendor is in a generated register.

**Negative / costs accepted**
- Better Stack is a new sub-processor to paper (DPA, region).

**Follow-up work created**
- Code: ADOT, dashboards and alarms with runbook links (Q-01-T25, S2); status page and on-call (Q-01-T41, S3); register and drift check (Q-01-T51, S4).
- Specs: SLO policy (ADR-093) and runbooks follow.
- Glossary: none.
- Matrix: none.
- Registry: `docs/operations/sub-processors.yaml` and generated `sub-processors.md`.

## Enforcement
- [ ] Lint rule: none.
- [x] Architecture / dependency rule in CI: egress host without a register row fails.
- [x] Test: dashboards and Sentry payloads carry no names or Restricted values.
- [x] Hook or protected path: the register is protected.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Logs, traces and alerts carry tenant UUIDs only. A new vendor needs a register row first.

**Do**
```
log.info("sync_done", tenant_id=tenant.uuid)
```

**Don't**
```
log.info("sync_done", firm_name=firm.name)
```

## Revisit when
A vendor's region or DPA fails review, or a fractional SRE partner (ADR-100) brings their own paging tool.

## Related
- ADRs: amends ADR-022's Decision, which names Sentry but no paging or status vendors (adds CloudWatch/X-Ray, Better Stack and the register); updates the sub-processor list in ADR-021; relies on ADR-094 and ADR-100.
- Plan: P-67; Q-01-T10, Q-01-T25, Q-01-T51; ch. 06 D-OPS-14 (chapter number P-41).
- Specs: none.
