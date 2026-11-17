---
id: TASK-8418
title: "C-01-T30: close.agent flux and planner modes"
spec: SPEC-655
acceptance_criteria: [AC-21, AC-22, AC-49]
risk_zone: red
status: in-review
branch: c01-t30-flux-planner-modes
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T30
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 F7, F2, §5. close.agent modes flux and planner (red): flux explanation runs whose drivers must foot to the code-computed change (repair, then needs_input) with verified citations; planner runs over 14 months of history choosing from the closed procedure and source option sets; outputs land as suggestions until a person adopts them.

## Plan (red)
1. `closes/agent.py`: modes `flux` and `planner` (prompts `close.agent.flux@v1`, `close.agent.planner@v1`); `DriverOut` (label with no figure, fact ids) and `settle_drivers` (offered `c`/`p` line facts once each, code's sums foot to `change`, else `drivers_do_not_foot`); `PlanChoiceIn`/`PlanRowOut` and `settle_rows` (one procedure and one source from the row's sets, once per account); fake responses (Payroll 4,350 + 1,850 + 1,470).
2. `closes/agent_runs.py`: `explain_line` (line facts from both months' registers, sign calibrated to the activity; one repair; escalated when it never foots; `ledger_line` citations code verifies for every line used, else escalated; a P-35 suggestion on `analytic_line` and an agent-authored `explained_draft` explanation) and `draft_from_history` (balance-sheet accounts with closed sets by account type, 14-month profile counts, a draft version drafted by the person with `drafted_by_run_id`, each row carrying its suggestion so publish needs adoption); suggestion targets `analytic_line`, `close_plan_version`. Synthetic firms only; `closes.agent` off is 404.
3. `plans.new_agent_draft`; flux view shows agent drafts as `explained_draft` with drivers; accept refuses an agent-authored newest explanation.
4. Routes: POST `/analytic-lines/{id}/explain`, POST `…/close-plan/draft-from-history` (409 `planner_did_not_draft` with the run id).
5. Spec: `trial_balance.read` added to close.agent's task scope (the citable authorises the actor); `_specs_v2.py` and `_eval_suites.py` regenerated; the two prompts on the frozen `evals/close_agent` suite.
6. Tests: `tests/unit/closes/test_c01t30_flux_planner.py`; the C-01-T29 fixture gains the new modes' facts.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5413). Lint, pyright, banned patterns and spec codegen check clean; app and worker import. Red: inline security review in the end pass. Partial: runs are inline (code-driven capability runs, as A-09-T29), not P-10 child runs with SSE; the escalated run raises no decision card yet (the run row says escalated and the route returns its id); the live eval run is `make evals` (costs money) and was not run. Gates and tests run once at the S48 end pass (build first, test last).
