---
id: ADR-148
title: Entitlements, agent-minutes and two-layer budgets
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-069 and ADR-070 assume per-engagement pricing, and `ff.*` module flags behave like plans. Accrued sells plans, seats and modules, and customers see agent-minutes, not model spend. Plan decisions DEC-51 and DEC-55 settle this; this ADR is P-28 in the plan's ADR backlog (AG-15 in the agent chapter).

## Decision
- **Entitlements are database rows.** Plans, seats and modules (for example `ff.attest`, `ff.internal_audit`, `ff.insights`, `ff.office_addins`) become entitlements. ADR-089 flags are used only for in-progress rollout, live at most 90 days, named `area.feature`.
- **Agent-minute = measured active step time.** Parallel steps are summed and every wait is excluded. One integer per run. The usage month follows the contract.
- **Two layers.** USD stays an internal safety layer and is never shown to customers. The customer layer counts agent-minutes: alerts, pre-run estimates, engagement budgets.
- **At 100% of the allowance,** scheduled runs pause unless the firm chose "keep running (overage)", which still stays inside the USD safety caps. Open sessions are never stopped.

## Options considered
### Option A: measured active step time, with entitlements in the database — chosen
- Pros: matches durations on screen; no estimation; plans change without a deploy.
- Cons: slow tools consume minutes without model cost (contained by excluding backoff waits and a margin KPI).

### Option B: wall-clock minutes
- Pros: simple.
- Cons: counts waits on people and inputs.
- Why rejected: customers would pay for waiting.

### Option C: minutes converted from USD
- Pros: tracks margin exactly.
- Cons: contradicts run durations shown on screen.
- Why rejected: plan DEC-51 chose measured active time.

## Consequences
**Positive**
- Module access, seats and allowances are data; flags no longer double as plans.

**Negative / costs accepted**
- A second metering path next to USD attribution; nine existing flags need renewal or retirement.

**Follow-up work created**
- Code: `plans`, `tenant_entitlements` and `require_entitlement` in the `platform` module (epic F-03, S3; task F-03-T28); renew or retire the 9 flags expiring 5-13 Jan 2027 in the Dec 14-18 bundle (F-03-T37, S4); agent-minute ledger written from run-completed events (epic P-10, S29-S38).
- Specs: ADM-14, INS-01/02, ENG-06, SHT-04 read usage from the ledger; no screen shows dollars.
- Glossary: Agent-minute (metering unit, owned by `platform`).
- Matrix: a route guarded by `require_entitlement` answers 403 with UI reason `entitlement` (F-03, S3).
- Registry: `docs/architecture/feature-flags.yaml` loses module flags; entitlement keys are a fixed list.

## Enforcement
- [x] Lint rule: new `ff.*` module flags are banned (F-03-T28).
- [x] Test: an entitlement-guarded route returns 403 for a firm without the module.
- [x] Test: ledger totals foot because rollups sum the stored per-run integers.
- [x] Hook or protected path: the flag registry check fails expired flags (ADR-089).
- [ ] Advisory only: none.

## Guidance for agents
Gate a whole module with an entitlement. Use a flag only for unfinished behaviour. Never show or log customer-facing USD.

**Do**
```python
@router.get("/v1/audits", dependencies=[require_entitlement("attest")])
```

**Don't**
```python
if flag("ff.attest"): ...   # a module is an entitlement
```

## Revisit when
Pricing changes shape, or a capability's USD cost per minute drifts below its floor for two consecutive usage months.

## Related
- Plan: P-28 (section 9.4.2); DEC-51 (open in `docs/product/decision-log.md` at time of writing; the plan's recommended option is taken); DEC-55 (decided); AG-15.
- Amends ADR-069: its budget hierarchy (call, run, engagement, firm per month, platform per day; soft and hard limits) stands as the USD safety layer. A customer layer in agent-minutes is added beside it.
- Amends ADR-070: per-call attribution and cost regression gates stand. Its target "AI cost is at most roughly 10% of the engagement price" no longer rests on per-engagement pricing.
- Amends ADR-089: its clause "New behaviour ships behind feature flags and is enabled per firm" is narrowed to rollout flags. The owner and expiry clauses stand.
