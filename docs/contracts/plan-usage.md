# Plan & usage (v1)

| Field | Value |
|---|---|
| Register row | epic contract (G-04 §8.1; registers one C13 gate kind and C16 kinds) |
| Version | v1 |
| Status | stub (G-04-T03) |
| Provider epic | G-04 (AY: plan, alerts, plan requests, billing rates) |
| Consumers | ADM-14, ADM-01 and ADM-02 (Add seats), K-03 (agent columns), W-03 (schedules), I-03, I-04 |
| Flag | `platform.plan_usage` (per firm) |
| Spec | `docs/specs/SPEC-680-g04-platform-console-plan-usage-support.md` (AC-26 to AC-43) |
| ADRs | ADR-148 (P-28), ADR-147, ADR-145, ADR-139; DEC-89 (no prices) |

## 1. Purpose
The firm's plan and seats, agent-minute usage against the included minutes, the budget alerts and At 100% policy, engagement alert rows, billing rates from the firm's practice-management system, and "Request more" with partner approval.

## 2. Who may call it
Every route answers, in order: a client principal 404; the action on the firm; 404 while `platform.plan_usage` is off; then 501 naming G-04-T11. Code: `backend/src/abacus/modules/platform/plan_usage_contract.py`.

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Plan | GET `/v1/firm/plan` | `plan.read` | T11 |
| Billing contact | PUT `/v1/firm/plan/billing-contact` | `billing_contact.manage` | T11 |
| Budget alerts | GET · PUT `/v1/firm/budget-alerts` (`version`, fresh MFA; 409 `stale_version`) | `plan.read` · `budget_alert.manage` | T11 |
| Engagement rows | GET `/v1/firm/engagement-budgets?alerting=true` (`visible()`, no hidden counts) | `usage.read` | T11 |
| Billing rates | GET `/v1/firm/billing-rates` (`{connected:false}` before I-04 on a real firm) | `plan.read` | T11 |
| Plan requests | GET · POST `/v1/firm/plan-requests` (Idempotency-Key) | `plan.read` · `plan_request.create` | T11 |
| Decide | POST `/v1/firm/plan-requests/{id}/approve` · `/decline` (409 `plan_request_self_approval`, `plan_request_not_pending`) | `plan_request.approve` | T11 |
| Withdraw | POST `/v1/firm/plan-requests/{id}/withdraw` | `plan_request.create` | T11 |
| Usage (P-10, additive) | GET `/v1/firm/usage?month=` adds `next_alert`, `alerts_sent[]`, `over_included`, `at_100_behaviour` | `usage.read` | T11 (split PR) |

**In-process read:** `platform.api.over_limit_policy(tenant) -> (at_100_behaviour, over_included: bool)` for the admission hook (G-04-T08); schedule-triggered runs only (OQ-2).

## 3. Models
`FirmPlanOut`, `SeatsOut`, `BillingContactIn`, `BudgetAlertsOut` / `BudgetAlertsIn`, `AlertRuleOut` / `AlertRuleIn`, `EngagementBudgetsOut`, `BillingRatesOut` (`BillingRateBandOut`: firm rates, `confidential`; `None` reads "Non-chargeable"), `PlanRequestIn`, `PlanRequestDeclineIn`, `PlanRequestOut`, `PlanRequestsOut`. Fixture footings (`platform/g04_fixtures.py`): 14,920 = 8,640 + 4,610 + 1,420 + 120 + 130 of 20,000 (74.6%, next alert 75% in 80); 18,240 (91.2%, 1,760 left); 20,860 (104.3%, 860 over); Granite Peak 1,240 of 1,500 (83%); rate bands 7 + 7 + 11 + 19 + 2 = 46.

## 4. Status words and gates
`plan_request` (DF-31); C13 gate kind `plan_request` awaiting partner approval. No price, overage amount, payment or invoice (P-27); agent-minutes never read as hours.
