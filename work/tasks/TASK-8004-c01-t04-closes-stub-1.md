---
id: TASK-8004
title: "C-01-T04: closes contract stub PR 1 — portfolio, record, runs, plans"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: c01-t04-closes-stub-1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T04
---

## Objective
closes contract stub PR 1 — portfolio, record, runs, plans.

## Plan
1. [x] `closes/contract.py`: Pydantic CloseRow, CloseTiles, CloseSummary, CloseRunView (over C6 v2), ClosePlan, ClosePlanVersion, PlanRow, RequestTemplate, CloseTemplate VMs with classification tags.
2. [x] 501 routes behind `closes.engine` for the portfolio, record, status, assignees, generate, runs, retry, plan, drafts, publish, request-publish, draft-from-history, adopt, templates (epic §4.3), each with one matrix action.
3. [x] `closes.api.register_status_guard` fail-closed slot and `close_for` facts signature.
4. [x] `docs/contracts/closes.md` part 1; contracts README row.
5. [ ] E0 fixtures (T12) and handlers typed against the stubs.
Rollback: revert; routes are flag-gated 501s.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: `closes/contract.py` (23 routes behind `closes.engine`, each one matrix action, human-only routes refuse non-humans 403 before 501), the VMs with classification tags, refusal classes `accounts_not_reconciled`, `run_in_progress`, `transition_not_available`, `plan_version_pinned`, `unadopted_rows` (error-codes.yaml regenerated), the consumer API (`CloseFacts`, `close_for`, `register_status_guard` / `status_guard` failing closed), `docs/contracts/closes.md` part 1 and the contracts README row; route introspection regenerated.
- **Partials.** Routes answer 501, not fixtures: the Copperleaf figure book is C-01-T13 (S45), so the FE serves CLS-01/02/09 from fixture handlers (T12). The generated client is regenerated once after T07 (all three stubs). A stale If-Match answers 409 `stale_version` (the repo's code), not the epic's 412.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
