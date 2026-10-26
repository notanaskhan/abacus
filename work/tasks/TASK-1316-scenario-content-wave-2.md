---
id: TASK-1316
title: Scenario content wave 2 through service APIs (P-07-T40)
spec: SPEC-307
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T40
branch: s10-p07-t40-scenario-wave2
created: 2026-10-26
updated: 2026-10-26
---

## Objective
`make seed-demo SLICE=acceptance` loads, idempotently and through the owning services, the
Northwind contacts, team and EQR history, independence state, the Harborline conflict checks,
the Thornbury and Meridian acceptance records and the questionnaire templates that CLI-04,
CLI-07, CLI-08 and ENG-05 read live.

## Plan
- `brightwater_hale/acceptance.py`: the slice's content (verbatim from the CLI-06, CLI-07 and
  CLI-08 handoff specs and the ENG-05 and CLI-04 fixtures) and its events.
- `loader.py`: one handler per event kind; `SLICE_NEEDS` gains `acceptance: (people,)`.
- `engagements/api.py`, `organisations/api.py`: export the services the loader calls
  (`create_draft`, `start_acceptance`, the acceptance prepare calls, `add_to_team`,
  `change_team_role`, `remove_from_team`, `approve_team`, `team_approval`, `assign_eqr`,
  `approve_eqr_eligibility`, `create_contact`, `RoleAsked`, `run_conflict_check`).
- Questionnaire templates bootstrapped (no service); everything else through services.
- No migration, no matrix or flag edit. Rollback: revert; a loaded database keeps its rows.
- Gaps and tensions: DEC-412.

## Tests (end of the run)
- Load `--slice acceptance` twice on a throwaway database: the second run replays nothing.
- Read back: the Thornbury record (Accepted with conditions at the 2026-09-24 snapshot, three
  conditions owned by Samuel Ito), the Meridian continuance, the A1 roster hours and EQR, and the
  Harborline clearances.

## Progress log
- 2026-10-26: built (build-first; the load test at the end of the run).
- 2026-10-26: `tests/integration/test_scenario_acceptance.py` passes (load at 2026-09-24, read
  back, second load writes nothing). The load found four service rules the build had not met,
  each fixed in the slice and recorded in DEC-412: no EQR eligibility approval (TW passes the
  competence check; Celia Marsh holds no `quality_partner`); Grace starts the Thornbury intake (a
  manager may not hold `engagement.create`); CLI-06h's search runs on the Thornbury client (a
  draft's checks are its creator's alone); the fee section is answered rather than a manual check
  asked of Grace (no service gives her `client_service` on an engagement). MO's confirmation is
  the slice's, since A1 is in planning and audit_core confirms nobody. Loader, compliance and
  people slice tests still pass; import contracts kept.
