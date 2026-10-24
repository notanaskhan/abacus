---
id: TASK-1198
title: Engagement hold and resume routes with a reason, for ENG-02's On hold control (carried from P-07-T28)
spec: SPEC-321
acceptance_criteria: [AC-11]
risk_zone: amber
status: in-progress
epic: P-07
plan_key: P-07-T28
branch: s8a-team-roles
created: 2026-10-25
updated: 2026-10-25
---

## Objective
ENG-02's status menu "Active ⇄ On hold…" (reason code required) has no route (DEC-272). Land `POST /v1/engagements/{id}/hold` and `POST /v1/engagements/{id}/resume` over F-03-T13's `transitions.hold` and `resume` so wave B can build the control.

## Plan (amber zone)
- **Routes:** in `engagements/contract.py` behind `engagements.v2`: `POST …/hold` `{reason}` (the five `HOLD_REASONS` codes, as a Literal) and `POST …/resume`, action `engagement.hold` (engagement partner, manager, `mfa_recent`), response `EngagementStatusOut {engagement_id, status, hold_reason}`; one unit of work each through `transitions.transition` (authorise inside, `engagement.held` / `engagement.resumed` audited, `engagement.status_changed` emitted); 409 `illegal_transition` from any other state (archived included), 422 `hold_reason_required`.
- **Human-only register:** unchanged. `engagement.held` is not one of I-AGENT-NEVER's verbs and the register does not list it; the transition table already refuses an agent or system principal before anything is written (INV-1).
- **Tests:** `tests/integration/test_engagement_hold.py` (hold with reason, resume, archived 409, missing reason 422, agent principal refused, audit and outbox); app gate 200 list; regenerate.
- **Rollback:** revert the commit; no migration.

## Progress log
