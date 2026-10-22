---
id: TASK-373
title: Client access grants, contract step - every client role read from grants (F-03-T26)
spec: SPEC-015
acceptance_criteria: [AC-8]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T26
branch: f03-t26-contract
created: 2026-10-22
updated: 2026-10-22
---

## Objective
ADR-146's contract step after TASK-372: client access is read from `client_access_grants` only,
and `engagement_members` narrows to staff roles (plan R9: the legacy client hub reads grants in
the same change).

## Plan (red)
- identity repository: `client_access_grants` table object, `GRANT_ROLE_OF` / `MATRIX_ROLE_OF`
  (owner = `client_admin`, contributor = `client_contributor`), `client_grant_engagements`
  subquery; `engagement_role` falls back to the grant; `client_admin_ids` and `client_contacts`
  read grants; `grant_engagement_role` (new or reactivated, with its event row).
- authz `visible()` / `visible_items()`: client roles reach through grants, staff through the
  team table. Matrix role names unchanged, so every module's checks stay as they are.
- invitations: acceptance writes the grant (`client_access.granted`, `access.changed`);
  removal emits `access.changed`.
- Migration 0084: make sure of every client row as a grant, delete the rows, narrow the CHECK,
  drop the mirror, `remove_client_member` revokes grants (with events), a grant needs a client
  membership. Downgrade restores the rows and 0083's mirror.
- Tests that encoded the storage (SQL shapes, seeds) move to grants with the same intent.
- Rollback: revert, downgrade 0084.

## Definition of done
- [x] `tests/integration/test_client_access_grants.py`: backfill and contract down/up, removal
  and re-invitation through the real functions, client roles refused on the team table, grants
  refused for staff, Meera Shah
- [x] Backend unit suite; integration, security, acceptance and contract suites
- [x] `make check-fast`

## Progress log
- 2026-10-22: built in one session.
