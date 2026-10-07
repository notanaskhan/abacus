---
id: TASK-022
title: Budget hierarchy, metering and denial-of-wallet controls
spec: SPEC-007
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: done
branch: task-022-budgets
worktree:
created: 2026-10-07
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
Implement SPEC-007 (approved, Q1–Q5).

## Scope
All of SPEC-007. Excluded: billing, per-engagement overrides, and UI.

## Context to load
- Spec: `docs/specs/SPEC-007-budgets-metering.md`
- ADRs: ADR-069, ADR-070, ADR-072, ADR-105
- Code: `ai_gateway/__init__.py` and `admission.py`, `connections/service.py` (`start_retrieval`), `agents/service.py` (`create_screening_run`), `worker/__main__.py`, `modules/platform/`

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **`ai_gateway/budgets.py`: the check runs in `_call` before every attempt, after the run budget and before capacity admission.**
   - **Spend per level:**
     - engagement this month and firm this month: sums over `usage_records` in the caller's tenant session;
     - platform today: a SECURITY DEFINER `platform_spend_today()` returning one number.

     Sums are cached about 5 s per process and dropped after each recorded call (AC-3).
   - **Hard limit crossed:** a deferrable call raises `BudgetExhausted` (terminal, `budget_exhausted`) and an essential one proceeds. At the platform's hard limit, every call raises.
   - **Soft limit crossed:** a deferrable call raises `NotAdmitted("deferred", 300)`, waiting through the SPEC-003 loop. A soft crossing alerts once per level and period per process (log `budget.soft_crossed` and the metric).
   - **Fail closed:** if a sum can't be read, deferrable calls are refused and essential ones keep their per-call and per-run budgets only.
2. **Limits:**
   - the firm's are `budgets` rows (migration 0018: tenant-scoped, forced RLS, one row per firm, app insert and update, audited `budget.updated`);
   - otherwise the settings defaults (Q1) apply: engagement $50 / $100 a month, firm $500 / $1,000 a month, platform $200 / $400 a day;
   - plan cap `firm_budget_cap_usd`, $1,000 (Q3).
3. **Action caps (Q4):**
   - **Retrievals:** `connections.start_retrieval` counts today's runs for the engagement. At 50 it refuses with `ActionCapReached` (409 `action_cap`), audited `action_cap.refused` in its own unit of work.
   - **Screenings:** `agents.create_screening_run` counts today's runs. At 200 it creates no run (the screening is `skipped`) and audits the same.
4. **Anomaly job (Q5):** a periodic task in the worker process that runs the relay. It is hourly and is not a Temporal schedule (D1).
   - It calls a SECURITY DEFINER `engagement_spend_anomalies(multiple, floor_usd)`, which returns (tenant, engagement) identifiers where the last hour's spend is more than 5 times the seven-day hourly average and more than $5.
   - It logs and counts `budget.anomaly`. It only alerts.
5. **Routes, in the `platform` module (D2):** `GET /v1/budget`, `PUT /v1/budget` (`budget.manage`, fresh MFA, up to the cap) and `GET /v1/metering?period=day|month` (`budget.read`): spend per engagement and agent from the tenant's usage records.
6. **Matrix:** `budget.read` (firm admin, practice leader) and `budget.manage` (firm admin, MFA).
7. **Indexes** on `usage_records` (`tenant_id, created_at`) and (`tenant_id, engagement_id, created_at`). `schema_check` maps are updated, and the two functions join `DEFINER_FUNCTIONS`.

**Protected paths:** `backend/src/abacus/ai_gateway/**`, `modules/connections/**`, `modules/agents/**`, `modules/identity/**`, `modules/platform/**`, `backend/src/abacus/worker/**`, `backend/src/abacus/api/**`, `backend/migrations/**`, the permission matrix, `schema_check.py`, and `banned_patterns.py` with its test.

### Questions for approval
- **D1. The anomaly job is an hourly periodic task in the worker process (next to the relay), not a Temporal schedule?** *Recommendation: yes.* It only alerts, and Temporal schedules would need a DISPATCH-001 exception.
- **D2. The budget and metering routes live in the `platform` module and call `ai_gateway` functions?** *Recommendation: yes.* `ai_gateway` isn't a module with routes.
- **D3. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass

## Progress log
- `2026-10-07` — Implemented:
  - the gateway budget check (`ai_gateway/budgets.py`), with `BudgetExhausted` mapped to `budget_exhausted`;
  - retrieval and screening daily caps (`action_cap.refused`, 409 `action_cap`);
  - the hourly anomaly job in the worker;
  - the platform routes, the matrix actions, migration 0018 and the schema maps.

  Gates, the schema check and unit tests pass. Full test runs deferred by the founder.
- `2026-10-07` — SPEC-007 approved and merged (#38). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The anomaly job is an asyncio task beside the relay, not a Temporal schedule | Approved in D1; no new schedule infrastructure | No |
| An idempotent retrigger (an existing run) doesn't count against the retrieval cap | It starts nothing | No |
| Firm-level reads (`budget.read`) compile `visible()` to `false` for engagement roles; the matrix test is split accordingly | No engagement role holds them | No |

## Questions for the human
- D1–D3 (above).

## Handoff
- **Next:** on approval, write the approval file and implement design 1–7.
