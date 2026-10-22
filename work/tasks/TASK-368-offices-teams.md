---
id: TASK-368
title: Offices, teams and membership attributes; firm role security_admin; engagement roles eqr_reviewer, specialist, client_service (F-03-T23)
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T23
branch: f03-t23-offices
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Brightwater Hale's three offices and 46 memberships are representable with levels, and a test
proves office is never an access predicate."

## Plan (red)
- Migration `0080_offices_teams_member_attributes` (next free on main):
  - `offices`, `teams`, `team_rosters` (organisations; tenant tables with RLS; insert-only for the
    app except roster rows, which may be removed);
  - `memberships`: `level` (partner, manager, senior, staff, seasonal, admin), `office_id`,
    `service_lines` (audit, tax, cas, advisory), `offshore`, `initials`; a client membership
    has no level or office;
  - firm role `security_admin` on memberships and staff invitations; engagement roles
    `eqr_reviewer`, `specialist`, `client_service`;
  - `engagements.office_id` references `offices`.
  - Downgrade restores every constraint. Checked: migrate with roundtrip and `schema_check` clean.
- Code: organisations models and registry; `FirmRole` and `EngagementRole`; the matrix role list
  (the new roles hold no allow until F-03-T24 grants them); `make generate`.
- Rollback: the downgrade, then revert.

## Decisions
- DEC-125: `team_rosters`, not `team_members` (the glossary bans the latter as a code name).
- Level eligibility (only a partner may be engagement partner or EQR reviewer) is the service's
  check with the role catalogue in F-03-T24, not a database trigger here.

## Definition of done
- [x] `tests/unit/identity/test_office_not_access.py`: the authorisation package, `visible()` and
  the matrix never read an office
- [x] `tests/integration/test_offices_teams.py`: three offices, 46 levelled memberships (22, 14,
  10), the new roles, attribute constraints, an office belongs to one firm
- [x] Backend unit and acceptance suites; web typecheck and tests (795); `make check-fast`
