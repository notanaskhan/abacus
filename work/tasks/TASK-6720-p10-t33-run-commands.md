---
id: TASK-6720
title: "P-10-T33: run command endpoints (plan, questions, redirect, retry, stop, sign-off, feedback) and run notifications"
spec: SPEC-647
acceptance_criteria: [AC-W1, AC-W2, AC-W5, AC-W6, AC-W7, AC-W10]
risk_zone: red
status: in-review
branch: s35-p10-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T33
---

## Objective
Agent and system contexts get 403 and the database refuses the row on plan approval and run sign-off, and Hannah Leclerc's approval moves the run to dispatched with one audit event.

## Plan (red: written before the build)
- `backend/src/abacus/modules/agents/commands.py` (new, PROTECTED agents): the only writer of a plan
  decision (PLAN-001). Each command: the route's matrix action on the run's engagement
  (`runs._run`, walls first), `require_live_human` (no agent, system, client or support context),
  then the row in one unit of work with one audit event, then the workflow signal.
  - Plan approve, edit, cancel: a new insert-only `agent_plans` version against
    `expected_version` (409 `plan_version_conflict`); an edit keeps and reorders the newest
    version's keys (422 `plan_edit_invalid` for a new, repeated or depended-on-and-dropped key);
    `plan_decided` while the run awaits approval, `redirected` for an approval later (AC-W10).
  - Question answer (one option, or free text where `other_allowed`; 422 `answer_invalid`) and
    skip; 409 `question_not_open`; signal `question_answered`.
  - Redirect (`messages`): a `user` item holding the note's fingerprint only (run events stream
    as stored); signal `redirected`. Retry one failed step (`run_commands.retry_step`). Stop.
  - Sign-off of an ended run: every open issue (latest failed step) and open decision (held card)
    acknowledged by id (409 `sign_off_unacknowledged`); one `run_sign_offs` row; `agent_runs`
    `signed_off_by/at`. Feedback: one thumb per person and step (insert-only).
  - `RunState`/`run_actions`: C6 v2 `allowed_actions` narrowed by the run's state.
- `runs_v2_contract.py`: the ten command routes call `commands`; `errors` keep 501 (stub rule).
- Notifications (C16): `run_needs_input` and `run_finished` registered (agent kinds, no inline
  action); `set_state` emits `agent_run.needs_input` (awaiting plan approval, needs input, waiting
  on inputs; to the person the run runs as, else the initiator), `agent_run.ready_for_review` and
  `agent_run.failed_v2` (to the initiator); catalogue lines and fixed templates.
- Registries: `error-codes.yaml` (7 new codes, `answer_invalid` gains a raiser), REVIEWED_FALLBACK
  (9 actions), banned pattern PLAN-001 (`INSERT INTO agent_plans` only in commands, record_plan and
  the synthetic recorder), `test_catalogue.py`'s closed list (+3 events).
- No migration: 0681's CHECKs already refuse a non-human decision and sign-off row.
- Tests: `tests/unit/agents/test_p10t33_commands.py` (edit rule, allowed actions, live human) and
  `tests/integration/agent_tests/test_p10t33_run_commands.py` (the row's acceptance over HTTP and
  the service; DB refusal for agent and system actors; stale version, edit, answer, sign-off,
  redirect and stop).
- Rollback: revert the PR; the flag `agent_runtime.v2` (off by default) hides every route (404).

## Partials (flagged)
- The redirect note's text is not kept anywhere: the run event holds its fingerprint only, and no
  model reads it until P-10-T40's model plan; the plan change of "hold sampling until Monday" is a
  person's plan edit plus approval (AC-W10 through `plan/edit`).
- Capabilities (`GET /v1/agents/capabilities`), auto mode and the engagement run stay 501 (their
  rows: P-10-T39/T40).
- Email templates `notification.run_needs_input` and `notification.run_finished` are content: import
  per environment (human to-do); until then their emails settle `suppressed`.

## Progress log
- 2026-11-10: built per the plan; tests written, not yet run (S35 end pass runs them).
