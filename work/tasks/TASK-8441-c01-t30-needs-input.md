---
id: TASK-8441
title: "C-01-T30: rest: an escalated close.agent run asks its person"
spec: SPEC-655
acceptance_criteria: [AC-49]
risk_zone: red
status: in-review
branch: s48r-close-needs-input
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T30
---

## Objective
C-01-T30 asks for repair, then needs_input; an escalated run ended silently (it read needs_input in C6 v2 but no one was told). end_capability_run now emits agent_run.needs_input for an escalation, so C16 run_needs_input reaches the initiator (and, for a close run, C-01-T26's close_run_needs_input).

## Plan (red)
1. agents.capability_runs.end_capability_run: on escalated, emit RunNeedsInput(run, engagement, initiator).
2. Unit test: only an escalation emits it.
3. Keep the runs inline (DEC-5409): the child-run/SSE form is not built, recorded below.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5429). Applies to every inline capability run (ledger.tb_mapper too). Not built: converting the flux and planner runs into P-10 child runs with SSE progress; they stay inline capability runs per DEC-5409 (the route returns the outcome in the same request), a later row if streaming is wanted. Security: the event carries identifiers only; no agent action decides anything. Gates and tests run once at the S48 end pass (build first, test last).
