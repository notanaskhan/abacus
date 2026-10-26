---
id: TASK-1318
title: Q-02-T06 to T08 gaps - staff stage route, make agent-stage, cross-process boundary clear
spec: SPEC-036
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T07
branch: s10-q02-agent-stage
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Close the reconcile's Q-02-T06..T08 code gaps: a staff stage route, `make agent-stage`, and the
boundary-cache clear reaching the worker through an outbox event.

## Plan
- Migration 0181 (`down_revision` 0180): `agent_stage_set(uuid, text, text, text, text)` SECURITY
  DEFINER, EXECUTE to `abacus_app` only. Rollback: downgrade drops the function.
- `agents/stage_admin.py` (`set_agent_stage`), `agents/stage_routes.py`
  (`PUT /v1/platform/agent-stages/{firm_id}/{agent_id}`, STAFF), mounted in `agents/api.py`.
- `ai_gateway/boundary.py`: `BoundaryFactsChanged` and `on_boundary_facts_changed`; emitted by
  opt-in/out (`identity/firm_settings.py`), exclusion (`engagements/service.py`) and the stage
  route; subscribed in `agents/api.py`.
- `Makefile`: `agent-stage`. `protected-paths.md`: classification and baselines.
- Then `make generate` for the new route (end of run).
- DEC-414.

## Tests (end of the run)
- Route: staff 200; firm token 401/403; unknown firm 404; live before 50 runs / 14 days 409;
  uncleared agent 422; the audit row exists.
- Migration up/down/up on the local database.
- Relay: emitting `ai_boundary.facts_changed` clears the firm's cached facts.

## Progress log
- 2026-10-26: built (build-first).
