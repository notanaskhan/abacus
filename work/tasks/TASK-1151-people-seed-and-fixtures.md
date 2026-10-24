---
id: TASK-1151
title: People seed slice and fixtures — the `people` scenario slice, ADM-01 and ADM-02 fixture scenarios, footing tests (G-01-T06)
spec: SPEC-307
acceptance_criteria: [AC-1, AC-2]
risk_zone: amber
status: done
epic: G-01
plan_key: G-01-T06
branch: s7-g01-people
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Every artboard renders from a scenario and every footing figure is a passing seed test with no 47th name."

## Plan (amber zone)
- **Python slice** `scenarios/brightwater_hale/firm_people.py`, opt-in `people` (P-08-T14's portal pattern; SCENARIO_HASH unchanged): the seat total 46, the four teams, and each of the 46 seats' template, level (the ADM-02 band), title, team, service line and seasonal end (Oct 31, 2026); Felix Andersen's IT / Security template carries `security_admin`.
- **Loader:** `identity.seats_provisioned` and `identity.member_profile_set` go through identity's services (`provision_setting`, new `set_member_profile`) in a unit of work under the event's actor; `organisations.team_created` is bootstrapped like offices (no team service until G-01-T08). Staff memberships get one microsecond per ADM-02 row so the list keeps the screen's order.
- **TS:** `fixtures/seed/firm-people.ts` mirrors the slice and adds the fixture-only facts; `fixtures/handlers/firm-settings.ts`; scenarios `fixtures/scenarios/ADM-01.ts` (a-f) and `ADM-02.ts` (a-g); `roleTemplates.gen.ts` generated from `role-templates.yaml`.
- **Tests:** `tests/unit/scenarios/test_people_slice.py`, `tests/integration/test_scenario_people.py` (E0 + people slice foots on ADM-02's live services), `apps/web/src/fixtures/firm-people.foot.test.ts`.
- **Rollback:** the slice is opt-in; nothing loads it by default.

## Progress log
- 2026-10-24: built. Live E0 with `--slice people` reads 46 rows in bands 7/7/11/14/5/2, "46 of 46", templates 7/4/6/8/8/11/1/1, teams 16/21/7/2 (DB test). Fixture-only until their rows land: groups (T08), office codes, addresses, leads and returns (T08, T-02), wall reasons and approvers (T09), service-line policies (T12), the Nov 2 deactivations (T13), Lena Park's Jan 5, 2026 invitation (predates the firm's setup on the timeline), last-active times and Lena's sign-ins (no sessions are seeded; no IP is stored), the eleven At a glance rows and later epics' defaults (AC2.2).
- Deferred: ADM-03 a-h scenarios. Their handlers need T08's and T09's shapes live (offices, teams, walls v2); `firmOffices()` and `firmTeams()` are ready for them. The `remy-vidal` persona is in the seed already (row 44); the offshore state is T09's.
- Daniel Reyes's title is SHL-03's "Tax Partner" (one title per person), where ADM-02 shows "Tax (signer)" (TASK-397's open gap).
- 2026-10-24 (close): `pytest tests/unit tests/contracts tests/security` 26,399 passed, 4 xfailed; `make check-fast` green; web `vitest run` 1,466 passed.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-287 | What the people slice loads live and what stays fixture-only | No |
