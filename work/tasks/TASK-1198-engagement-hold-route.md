---
id: TASK-1198
title: Engagement hold and resume routes with a reason, for ENG-02's On hold control (carried from P-07-T28)
spec: SPEC-321
acceptance_criteria: [AC-11]
risk_zone: amber
status: done
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
- 2026-10-25: built as planned behind `engagements.v2` (DEC-328); `engagements-v2.md` row and ENG-02's API row updated. `test_engagement_hold.py` 5 passed (hold and resume with audit and outbox, archived and non-hold 409, staff, stale MFA and an agent refused with nothing written, 404 flag off, the API reasons equal `HOLD_REASONS`).
- 2026-10-25 (final checks on the branch): `uv run pytest tests/unit tests/contracts tests/security` 29,446 passed, 5 xfailed, 1 failed: `tests/unit/synthetic/test_generate.py::test_ac17_default_generation_and_exports_finish_within_five_seconds`, a 5-second timing test on a machine at load 16; the file passes alone (45 passed). Integration (targeted): 19 files incl. G2 v2, work items, engagements v2 live, drafts, human-only guard, assurance phase and the engagement/independence back-fills (`test_independence_gate.py`, `test_due_dates_and_delegation.py`, `test_p07t26_contacts_g2_independent.py` and others) 341 passed, 5 xfailed; earlier on the branch `test_engagements.py`, `test_engagements_schema.py`, `test_schema_check_db.py`, `backfill/test_team_management.py` 506 passed (the two C1 team-shape failures fixed and rerun green), `test_team_roles.py` + `test_engagement_hold.py` 12 passed. `make check-fast` green; web `tsc` clean; vitest `src/status`, `src/fixtures/contracts` 180 passed, ENG-02 26, legacy people and POR-02 22.
