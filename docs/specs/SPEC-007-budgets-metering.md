---
id: SPEC-007
title: Budget hierarchy, metering and denial-of-wallet controls
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-069, ADR-070, ADR-055, ADR-072, ADR-019, ADR-105]
related_specs: [SPEC-003, SPEC-005]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Model spend is bounded at every level ADR-069 names: per call, per agent run, per engagement, per firm per month, and platform-wide per day.
- **Soft limits** alert and degrade: deferrable work waits, and eligible cheaper tiers are used.
- **Hard limits** allow essential work only.
- **Other controls:** per-engagement action caps, the existing upload limits, and a spend-anomaly job stop denial of wallet.
- **Metering:** usage records already attribute every call (ADR-070). Metering summarises them per firm and engagement.

## 2. Problem and context
Today the gateway enforces a per-call budget and the run's budget (`_spent_by_run`). Nothing bounds an engagement, a firm's month or the platform's day. A runaway agent loop, a hostile upload that inflates context, or a bug that re-screens forever would spend without limit until someone noticed.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| The gateway | Checks every level before each call |
| Firm admins | Set the firm's monthly budget within the plan limit (Q3) |
| Platform operators | Set the platform's daily ceiling and the defaults; receive alerts |
| Agents | Declare `essential` (ADR-105); deferrable work waits under a soft limit |

## 4. Goals and non-goals
**Goals**
- Budgets at five levels, each with a soft and a hard limit (Q1). The gateway checks every level before each call, using its estimate.
- **Degradation order (ADR-069, ADR-072):**
  - at a soft limit, deferrable work is refused as `deferred` and waits through SPEC-003's admission loop, and cheaper tiers are used only when eligible (SPEC-005);
  - at a hard limit, only essential work proceeds, and deferrable work fails `budget_exhausted` once its class's maximum wait passes.
- **Per-engagement action caps:** retrievals and screenings per day (Q4).
- **Spend-anomaly job:** alerts when an engagement's spend rate passes a multiple of its normal rate (Q5).
- **Metering:** spend per firm, engagement and agent per day and month, readable by firm admins and operators.

**Non-goals**
- Billing and invoices.
- Changing tiers based on evaluation, which is SPEC-005's.
- Upload size and page limits, which already exist (evidence `ContentTooLarge`, the gateway's `DatasetTooLarge`). This spec only lists them.

## 5. User stories and acceptance criteria
### Story 1: Spend can't run away
- **AC-1** Given the five levels, when a call's estimate would take any level past its hard limit, then a deferrable call is refused `budget_exhausted` and an essential call proceeds, unless the platform's daily hard limit is reached, which stops everything. Nothing is sent to the provider.
- **AC-2** Given a level past its soft limit, when a deferrable call asks for admission, then it is refused as `deferred` (SPEC-003), and the run shows `queued` with reason `deferred`. Essential calls proceed.
- **AC-3** Given spend is counted, then it comes from `usage_records`, actual cost after each call (ADR-070). The check before a call uses committed spend plus the call's estimate.

### Story 2: Caps on actions
- **AC-4** Given an engagement at its daily cap of retrievals or screenings (Q4), when another is started, then it is refused with 409 `action_cap`, audited, with nothing started.

### Story 3: Someone notices
- **AC-5** Given a level crosses its soft limit, then an alert is raised once per level and period: a log event plus a metric (`abacus.budget.soft_crossed`). It carries identifiers only.
- **AC-6** Given an engagement's spend over the last hour passes the anomaly multiple of its trailing seven-day hourly average (Q5), when the anomaly job runs (hourly, as a background-class workflow), then `budget.anomaly` is logged and counted, and the engagement is flagged.

### Story 4: Who sees and sets what
- **AC-7** Given a firm admin with fresh MFA, when they set the firm's monthly budget within the plan's limit, then it's audited and applies to the next call. Nobody else can (a new matrix action, `budget.manage`).
- **AC-8** Given a firm admin, when they read metering, then they see spend per engagement and agent, per day and month, for their firm only (`budget.read`).

## 6. Behaviour and flows
1. The gateway estimates the call's cost (as it does today).
2. It loads the five levels' limits and their spend so far. Spend is cached per level for a few seconds and refreshed after each recorded call.
3. If a hard limit would be crossed: refuse deferrable work, or everything at the platform hard limit. If a soft limit is crossed: refuse deferrable work as `deferred`, which waits. Otherwise admit, and SPEC-003's capacity check follows.
4. After the call, usage is recorded as today.

## 7. Domain and data changes
- **`budgets`** (identity- or platform-owned, Q2):
  - one row per firm, with `monthly_soft_usd` and `monthly_hard_usd`;
  - platform and engagement defaults are settings;
  - per-engagement overrides are a later step.
- **Spend views:** sums over `usage_records` by tenant, engagement and period, with an index on (tenant_id, created_at) and (tenant_id, engagement_id, created_at).
- **Action caps:** counts of today's retrieval runs and screening runs per engagement, read from the owning modules' APIs.
- **The anomaly job:** a background-class workflow, hourly, using the Temporal schedule.

## 8. Interfaces
| Interface | Purpose |
|---|---|
| Gateway admission | The budget check before the capacity check (SPEC-003) |
| `GET /v1/budget` and `PUT /v1/budget` | The firm's monthly budget (`budget.read`, and `budget.manage` with fresh MFA) |
| `GET /v1/metering?period=…` | Spend per engagement and agent (`budget.read`) |

## 9. Authorisation and tenancy
- **New matrix actions:**
  - `budget.read`: firm admin and practice leader;
  - `budget.manage`: firm admin with fresh MFA.

  It is a protected change.
- **Tenancy:** firm budgets and metering are tenant-scoped (RLS). The platform's daily total is computed across tenants only inside a SECURITY DEFINER function returning one number (the TASK-018 D3 pattern).

## 10. AI behaviour
No new model calls. Every gateway call passes the budget check.

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **The budget store or the spend sums fail:** fail closed. Deferrable work is refused; essential work proceeds only within the per-call and per-run budgets.
- **Concurrent calls near a limit:** the check uses committed spend plus estimates, so it can slightly overshoot between refreshes, by at most one call per process. That is accepted and documented.
- **A new firm with no row:** it gets the default firm budget (Q3).

## 13. Security and privacy
- Spend data holds identifiers and amounts only (internal).
- Only firm admins set budgets.
- The platform ceiling is an operator setting.
- Denial of wallet is covered by the five levels, the action caps, the anomaly alerts, and the existing upload and context limits.

## 14. Audit trail and evidence integrity
`budget.updated` and `action_cap.refused` are audited. Usage records stay insert-only.

## 15. Observability
- **Metrics:** spend per level and period, `abacus.budget.soft_crossed`, `abacus.budget.refused` (by level and outcome), and `abacus.budget.anomaly`.
- **Logs:** identifiers only.

## 16. Performance and scale
One cached sum per level per call. The sums use indexed range scans. The anomaly job is hourly.

## 17. UX
API only in this spec. A budget page comes later.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-2 | unit + integration | Each level's soft and hard behaviour; essential versus deferrable; platform hard limit stops all |
| AC-3 | integration | Spend from usage records; estimate plus committed spend |
| AC-4 | integration | Retrieval and screening caps; 409; audit |
| AC-5, AC-6 | unit | Alert once per period; anomaly maths |
| AC-7, AC-8 | integration | Matrix, MFA, tenant isolation |

## 19. Rollout
Generous defaults (Q1, Q3), so nothing in local development or CI is throttled. The migration is additive.

## 20. Open questions
- [ ] **Q1: the levels' defaults (soft / hard).** *Recommendation:*
  - per call and per run: as today, from the agent spec;
  - per engagement: $50 / $100 a month;
  - per firm: $500 / $1,000 a month;
  - platform: $200 / $400 a day.

  All are settings, revisited with real usage.
- [ ] **Q2: owner of `budgets` and the spend functions.** *Recommendation:* `ai_gateway`, which already owns `usage_records` and enforces the limits.
- [ ] **Q3: who sets the firm budget.** *Recommendation:* a firm admin with fresh MFA, up to the plan's hard limit (a setting, default $1,000 a month). Raising the plan limit is an operator change.
- [ ] **Q4: action caps.** *Recommendation:* per engagement per day, 50 retrievals and 200 screenings. Settings.
- [ ] **Q5: anomaly rule.** *Recommendation:* the last hour's spend is more than 5 times the trailing seven-day hourly average, and more than $5. It only alerts; it never blocks.

## 21. Future / explicitly deferred
- Per-engagement budget overrides, and a budget and metering page.
- Billing.
- Automatic blocking on anomaly.
