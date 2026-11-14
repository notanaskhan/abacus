---
id: TASK-8004
title: "C-01-T04: closes contract stub PR 1 — portfolio, record, runs, plans"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: todo
branch: c01-t04-closes-stub-1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T04
---

## Objective
closes contract stub PR 1 — portfolio, record, runs, plans.

## Plan
1. [ ] `closes/contract.py`: Pydantic CloseRow, CloseTiles, CloseSummary, CloseRunView (over C6 v2), ClosePlan, ClosePlanVersion, PlanRow, RequestTemplate, CloseTemplate VMs with classification tags.
2. [ ] 501 routes behind `closes.engine` for the portfolio, record, status, assignees, generate, runs, retry, plan, drafts, publish, request-publish, draft-from-history, adopt, templates (epic §4.3), each with one matrix action.
3. [ ] `closes.api.register_status_guard` fail-closed slot and `close_for` facts signature.
4. [ ] `docs/contracts/closes.md` part 1; contracts README row.
5. [ ] E0 fixtures and handlers typed against the stubs.
Rollback: revert; routes are flag-gated 501s.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
