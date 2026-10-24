---
id: TASK-1150
title: People v2 — migration 0142, staff list on the envelope with bands and tallies, person drawer, attributes, role and security-role changes, deactivation, invitations v2, role-template grid (G-01-T05)
spec: SPEC-024
acceptance_criteria: [AC-3, AC-4]
risk_zone: red
status: done
epic: G-01
plan_key: G-01-T05
branch: s7-g01-people
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"ADM-02 a-f data is live with counts that foot to 46, and a role change is audited as Role changed by Grace Holloway."

## Plan (red zone)
- **Migration `0142_people_v2.py`** (down_revision `0133`):
  - `memberships` + `role_template` (CHECK the eight templates; NULL for client memberships and back-filled for staff from `firm_role` and `level`), `access_ends_on date`, `revoked_reason` (CHECK `manual`, `access_ended`, `scim_deprovisioned`), `revoked_on_behalf_of uuid`, `version int NOT NULL DEFAULT 1`. Column UPDATE grant to the app on `role_template, level, job_title, office_id, service_lines, access_ends_on, offshore, version` (firm roles and revocation stay behind the definers).
  - `staff_invitations` + `role_template`, `level`, `office_id` (FK offices), `team_ids uuid[]`, `service_lines text[]`, `access_ends_on`, `offshore`, `display_name`, `job_title`, with matching INSERT grants.
  - Definers: `membership_set_firm_role` (same signature) and `add_staff_membership` (same signature; back-fills the template on insert, clears the deactivation on reactivation) redefined; `membership_set_firm_role` also keeps the last `security_admin` (AC4.3). New `membership_deactivate(uuid, text, uuid)` (both guards, reason, on-behalf-of, ends the person's staff sessions with `membership_removed` when no other firm holds them), `staff_last_sign_ins()` and `staff_sign_in_history(uuid, integer)` (the session's firm's staff only). Registered in `schema_check.DEFINER_FUNCTIONS`.
  - Rollback: `alembic downgrade 0133` restores 0127's two bodies and drops the rest.
- **Code:** `identity/people.py` (list with bands, counts, tallies and filters; person; attributes; role; security role; deactivate; invitations v2 with seats; role-template grid); `identity/slots.py` gains the member-teams slot (organisations registers the reader and the writer over `team_rosters`); `identity/settings_contract.py` routes go live; `GET /v1/firm/staff` grows additively (v2 `items`, `counts`, `tallies`, keeping `members` and `invitations` for the legacy screen) and moves to `firm.read_people`; `PUT /role` takes `role_template`; `/revoke` becomes deactivate's alias; invitations take the v2 attributes. Seat total: the registered, provisioning-only setting `plan.seats` (DEC-285).
- **Role templates:** `docs/architecture/role-templates.yaml` gets the 16 grid rows; new generator `abacus_tools.codegen.role_templates` renders `identity/_role_templates.py` (in `GENERATORS`); drift and I-AGENT-NEVER tests in `tests/unit/identity/test_role_templates.py`.
- **Events:** `membership.deactivated` (new), `access.changed` on every role, attribute and membership change; audit `membership.role_changed` (actor names the person, INV-5), `membership.security_role_changed`, `membership.attributes_changed`, `membership.deactivated`, `membership.invited`.
- **Matrix:** no new action; `GET /v1/firm/staff` declares `firm.read_people`.
- **Tests:** `tests/integration/test_people_v2.py` (AC3.1 to AC4.7 against Postgres), the contract suite's `LIVE` set, schema expectations, the generated route introspection.

## Progress log
- 2026-10-24: built as planned, with these changes from the plan (DEC-285, DEC-286):
  - `GET /v1/firm/staff` grew the v2 envelope but **stays `firm.manage_users`** (fresh MFA): SPEC-024 AC-3's tests in `backfill/test_staff_people.py` hold it there, so partners and security admins don't read ADM-02a's list yet. The move to `firm.read_people` needs those tests amended in a protected bundle (open, for the main session).
  - `role_template` is nullable (36 test files insert staff memberships directly); a NULL reads the implied template. Seasonal-needs-an-end is the service's rule (a CHECK only on invitations).
  - Seats: `plan.seats`, a provisioning-only settings key (DEC-285), since entitlements have no firm-seat row.
  - `/revoke` keeps its `membership.revoked` audit name (the legacy test asserts it) and now uses `membership_deactivate`.
  - Grid: two rows the matrix grants differently today stay `source: policy` (methodology publish, create client/engagement); the drift test holds the seven `source: matrix` rows.
  - Not done here (their rows): assignments list in the drawer (count only; `register_active_engagements` providers), the annual status (T13), `membership.attributes_changed` as an outbox event (audit only), the access-end job (T13), `roleTemplates.gen.ts` (T10 reads the API).
- Tests: `tests/integration/test_people_v2.py` (14), `tests/unit/identity/test_role_templates.py` (12), contract suite (76), `backfill/test_staff_people.py` (34), `test_firm_settings_live.py` (4).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-285 | Entitlements carry no firm seat total | No |
| DEC-286 | The list's action, nullable templates, firm roles, grid sourcing, deactivation sessions | No |
