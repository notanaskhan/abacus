---
id: TASK-7401
title: "P-10-T49: API-level journey test test_runtime_v2_journey.py: J11 b2-b3, J23 step 1, J13 queue count includes the run's proposal; INV-1 to INV-5"
spec: SPEC-647
acceptance_criteria: [AC-W2, AC-W4, AC-W5, AC-S2, AC-S4, AC-P1, AC-P4]
risk_zone: red
status: in-review
branch: s38-p10-t49
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T49
---

## Objective
The test runs in make check and fails on any agent-actor decision, uncited approved change, walled
read or wrong attribution.

## Plan (red)
- Test `backend/tests/integration/agent_tests/test_runtime_v2_journey.py`: every human step over
  HTTP as the person; the workflows' steps as their activities in the workflow's order (load,
  `validate_plan`, `record_plan`, `set_state`, `execute_step`, the approved write after
  `not_before`); the model's turns are scripted `TurnOutcome`s (FakeModel), never a model.
  - J11 b2–b3: request → question (WB-01a) → answer (WB-01b) → one child run, plan with one
    declared write → Hannah approves (AC-W2) → build workbook and propose Save to Files through C17
    → J13 counts it → Hannah approves at 9:27 → nothing before +10 s, saved at +11 s as
    "Hannah Leclerc via Agent" (AC-P1) → counts back.
  - J23 step 1: #4127 started by Marcus, approved by Hannah, Running, then Planning materiality
    raises a card reserved to the engagement partner: Margaret's decisions band counts it,
    Hannah's does not (AC-W4 precondition).
  - INV-1 and INV-5 through `abacus_tools.harness.invariants.check` over the window, INV-1 at the
    decision tables, INV-2 on the approved proposal's rows, INV-3 for Lena Park (walled: 404 on the
    session and run, zero counts, no read event), INV-4 (no portal read in the window).
- Code the journey needed (C13 did not count v2 runs): `agents.gates` registers two gate sources,
  `agent_run_plan` (a v2 run in `awaiting_plan_approval` with an undecided newest plan, assigned to
  the person it runs as, `assigned_only`) and `run_proposal` (a v2 run's pending SHL-10 proposal,
  assigned to its routed approver, else the run's person); `agents.repository` the two reads;
  `commands._decide` emits `agent_run.plan_decided` (new `RunPlanDecided`); `review.gates`
  C13_EVENTS gains the eight events (DEC-4401). Shadow runs never count.
- No migration, no flag. Rollback: revert; the two sources' rows go `done` on the next rebuild.

## Partial
- J11 runs on an engagement-bound session: the firm-level Files store ("Files › Firm reports ›
  TY2025 season") is W-02's (TASK-6802 partial), so the saved copy lands in the engagement's
  Deliverables folder.
- The workflows are driven by their activities, not by a Temporal worker (the replay histories pin
  the command order); a worker-driven run of the same journey is the staging Playwright's
  (P-10-T50).
- Pinned sets to update at the end pass: C13 subscribed events, the gate-source registry list.

## Progress log
- `2026-11-12` — Built (S38). Lint and types clean; tests written, not run (end pass).
