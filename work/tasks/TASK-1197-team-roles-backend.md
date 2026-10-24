---
id: TASK-1197
title: Team and roles backend (ENG-05) - team_roles migration, EQR eligibility and approvals, team approval, portal visibility, confirmation requests; assignee team and wall checks (P-07-T30)
spec: SPEC-332
acceptance_criteria: [AC-13, AC-14, AC-16]
risk_zone: amber
status: in-progress
epic: P-07
plan_key: P-07-T30
branch: s8a-team-roles
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Thomas Whitcombe is ineligible as Fairhaven's EQR for cooling-off and Margaret Okonkwo cannot approve EQR eligibility on Margaret's own engagement" (P-07-T30), on the T29 contract (`docs/contracts/acceptance-independence.md` §ENG-05).

## Plan (amber zone)
- **Owed from S7 (first commit):** `engagements/work_items.assign_work_item` refuses an assignee who is not a staff member of the engagement or is walled from its client (404 `not_found`, the same answer for both, so a wall is never revealed), after `authorise(work_item.assign)` and before the G2 check. ED-042.
- **Migration `0155_team_roles.py`** (down_revision 0146): `engagement_members` + `budget_hours numeric(7,1) NULL CHECK >= 0`, `shown_on_portal bool NOT NULL DEFAULT false`, `proposed_at timestamptz NULL` (default `clock_timestamp()` for new rows; existing rows NULL); app UPDATE on `budget_hours, shown_on_portal` only. `team_member_set_role` and `team_member_remove` redefined to handle `specialist` (and `eqr_reviewer` for removal). New insert-only `team_approvals` (engagement_id, approved_by, approved_at, member_set_hash, `actor_kind = 'human'` CHECK) and `eqr_eligibility_approvals` (engagement_id, candidate_user_id, checks jsonb, result CHECK IN ('eligible','not_eligible'), approved_by, approved_at, `actor_kind = 'human'` CHECK), both tenant tables with forced RLS, trigger and revoked UPDATE and DELETE. `abacus_human_only_actions()` = 0135's 28 entries + `team.approved`, `eqr.eligibility_approved`; downgrade restores 0135's list and 0027's functions.
- **Registries:** engagements `registry.py` (tables, INSERT_ONLY, INSERT_COLUMNS); identity `registry.py` (engagement_members UPDATE_COLUMNS); `human-only-actions.yaml` + codegen; audit targets unchanged (target `engagement`).
- **Code:** `engagements/team.py` *(new)*: roster with budget hours, portal flag, proposed and independence state; `approve_team` (EP, human, hash of the member set, `team.approved`); `team_approval` (footer facts: approver, date, changed, added since); `set_portal_visibility` (`team.portal_visibility_changed`); `set_budget_hours` (with role changes); `eqr_candidates` (checks `not_on_team`, `cooling_off` (EP on this client in the two years before), `competence` (EP or EQR on an engagement of the same service line before), `independence` (declined here fails; otherwise pending), `capacity` (placeholder, not assessed)); `assign_eqr` (409 `eqr_on_team`, 409 `eqr_not_eligible`; replaces the current EQR; `eqr.assigned`); `approve_eqr_eligibility` (quality partner; 409 `eqr_approver_is_ep`; insert-only row; `eqr.eligibility_approved`); `remind_independence` (`independence.reminded`, the existing `independence.requested` event). Identity: `team.add_member` accepts `specialist`; `set_eqr` (insert/replace the EQR member row). Routes in `acceptance_contract.py` go live behind `engagements.v2`; the live team routes take `specialist` and `budget_hours`.
- **Tests:** `tests/integration/test_team_roles.py` (AC: Thomas cooling-off, Margaret not approving her own; EQR never on the team; team approval and changes-since; portal visibility; reminders; agent/system refused at the DB CHECK); `test_work_items.py`/`test_g2_v2.py` additions for the assignee checks; `test_schema_check_db.py` expectations; stub test marks the team rows live.
- **Rollback:** revert the commits; `alembic downgrade 0146`.

## Progress log
- 2026-10-25: owed from S7: `assign_work_item` now refuses an assignee off the team or walled from the client (404, after `authorise`, before G2); ED-042. `test_g2_v2.py` (2 new), `test_work_items.py`, `backfill/test_p07t26_contacts_g2_independent.py`: 35 passed, 1 xfailed.
- 2026-10-25: built as planned with these choices (DEC-327): the ENG-05 conflicts live in `engagements/team_errors.py` (shared by the service and `team.py` without a cycle); role facts come from identity (`team_standing`, `engagements_served`) so no role comparison sits outside identity (AUTHZ-001); the team routes return `TeamRosterMemberOut` and C1's projection keeps `TeamMemberOut` (adding the fields to `TeamMemberOut` changed `GET /v1/engagements/{id}`'s team shape and broke `test_ac4_firm_admin_and_practice_leader_create_an_engagement`); the reminders route is live behind `engagements.v2`; `competence` zero is `not_assessed`. `member_details_of` joins LIST_EXEMPT (a team read after `authorise`). Tests: `test_team_roles.py` 7 passed (AC: Thomas cooling-off 2024, Margaret refused as EP-approver); `test_schema_check_db.py`, `test_human_only_guard.py`, `backfill/test_team_management.py`, `test_engagements.py`, `test_engagements_schema.py` 506 passed then the two C1 shape failures fixed and rerun green.
