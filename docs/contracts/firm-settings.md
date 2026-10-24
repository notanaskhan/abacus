# Firm settings, people, roles, offices and walls (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (G-01) |
| Version | v1 |
| Status | overview and sections live (G-01-T04, 2026-10-23); people, role templates live (G-01-T05, 2026-10-24); the rest stub |
| Provider epic | G-01 (`identity`, `organisations`) |
| Consumers | ADM-01, ADM-02, ADM-03; SHL-03 (the profile drawer's annual confirmation); P-07 (G2 reads annual confirmations) |
| Freeze sprint | the sprint review after the stub |
| Flag | `firm_settings.v2` (default off, created 2026-10-23, expires 2027-04-21 under DEC-137) |
| Spec | G-01 (`docs/plan/epics/G-01.md` §3, §4.3); SPEC-002 amended by DEC-169 |
| ADRs | ADR-139 (P-36), ADR-024, ADR-026, ADR-031, ADR-005; DEC-30, DEC-43, DEC-52, DEC-73, DEC-91, DEC-132, DEC-169 |

## 1. Purpose
One family for the firm's own configuration: the settings frame and its typed sections (ADM-01), people, role templates and annual independence (ADM-02), offices, teams, groups, service-line separation, offshore and walls v2 (ADM-03). Walls keep 404 semantics: nothing here carries a hidden count or a field derived from walled rows (DEC-43). The firm's region is never writable through this family.

**Stub behaviour.** With `firm_settings.v2` off every route below answers 404. With it on, the overview, the sections (G-01-T04, DEC-170), the person, its writes and the role templates (G-01-T05, DEC-286) are live; the rest answer 501 `not_implemented` until their task lands: T08 (offices, teams, groups), T09 (walls v2), T12 (service lines, offshore), T13 (annual independence).

**Existing routes kept, growing additively in their tasks:**
- `GET /v1/firm/staff` (G-01-T05): the list envelope of `StaffRowV2Out` (`items`, `next_cursor`, `total`, `counts` per band over the filters less the band filter) with `tallies` (`StaffTalliesOut`) and SPEC-024's `members` and `invitations` kept for the legacy screen; filters `q` (name or email), `role_template`, `office_id`, `team_id`, `status`, `band`, `cursor`, `limit`. Still `firm.manage_users` with fresh MFA (DEC-286). A pending invitation is a row with `invitation_id` and no `user_id`.
- `POST /v1/firm/staff/invitations` takes the template, level, office, teams, service lines, access end, offshore, name and title (409 `seats_full` with `{used, total}`, `already_member`; 422 `access_ends_required`); the link lasts 14 days at the firm's business time. Resend and revoke unchanged.
- `PUT /v1/firm/staff/{user_id}/role` takes `role_template` (and optionally `level`; `firm_role` is then a partner's oversight role): template, level and firm role change in one unit of work, audited `membership.role_changed` as the person who made it.
- `POST /v1/firm/staff/{user_id}/revoke`: deactivate's alias for one release (same definer; audit `membership.revoked`).
- `GET` and `POST /v1/walls`, `POST /v1/walls/{wall_id}/remove`: their v2 shape is `WallV2Out`.

## 2. Who may call it
| Operation | Method and path | Matrix action |
|---|---|---|
| Overview | `GET /v1/firm/settings/overview` | `firm.read_settings` |
| A section | `GET /v1/firm/settings/{section}` | `firm.read_settings` |
| Save a section | `PATCH /v1/firm/settings/{section}` | `firm.manage_settings` (fresh MFA) |
| A person | `GET /v1/firm/staff/{user_id}` | `firm.read_people` |
| Edit a person | `PATCH /v1/firm/staff/{user_id}` | `firm.manage_users` (fresh MFA) |
| Security role | `PUT /v1/firm/staff/{user_id}/security-role` | `security_role.assign` (fresh MFA) |
| Deactivate | `POST /v1/firm/staff/{user_id}/deactivate` | `firm.manage_users` (fresh MFA) |
| Role templates and grid | `GET /v1/firm/role-templates` | `firm.read_people` |
| Annual independence | `GET /v1/firm/independence/annual?year=` | `independence.annual_read` |
| Confirm one's own | `POST /v1/me/independence/annual` | `independence.annual_confirm` |
| Service lines | `GET /v1/firm/service-lines` · `PUT /v1/firm/service-lines/{line}` | `firm.read_settings` · `service_line_policy.manage` (fresh MFA) |
| Offshore | `GET /v1/firm/offshore` | `firm.read_settings` |
| Offices | `GET` · `POST /v1/firm/offices` · `PATCH /v1/firm/offices/{office_id}` | `org_structure.read` · `org_structure.manage` (fresh MFA) |
| Teams | `GET` · `POST /v1/firm/teams` · `PATCH /{team_id}` · `PUT /{team_id}/members` | `org_structure.read` · `org_structure.manage` (fresh MFA) |
| Seasonal access end | `PUT /v1/firm/groups/seasonal/access-ends` | `firm.manage_users` (fresh MFA) |
| Wall preview | `GET /v1/walls/preview?user_id&client_id` | `wall.create` |
| Approve a wall | `POST /v1/walls/{wall_id}/approve` | `wall.approve` (named partner; fresh MFA) |
| A wall's events | `GET /v1/walls/{wall_id}/events` | `wall.list` |

Every action denies `agent` and `system`, and no client role holds any. G-01 §4.3 names `office.*` and `team.*`; one pair, `org_structure.read` and `org_structure.manage`, covers both, so no matrix rule names an office (DEC-30's guard, `test_office_not_access`). The widenings of live actions (`firm.read_settings` to security admins, `wall.create` and `wall.remove` to partners) land with G-01-T04 and T09, not with the stub.

## 3. Models
Code: `backend/src/abacus/modules/identity/settings_contract.py`, `backend/src/abacus/modules/organisations/settings_contract.py`. Every field is tagged (ADR-031).
- **Overview** `SettingsOverviewOut`: firm name, sections (key, group, visible, planned) and At a glance rows (key, tone, `facts` as counts by key, href, `unavailable` when its provider failed). Words come from the copy registry by key.
- **Section** `SettingsSectionValuesOut`: registered keys with values, `version`, `read_only_reason`, `allowed_actions`. Plan & seats is absent for `security_admin`. `SettingsPatchIn` takes `version` and registered keys only.
- **People** `StaffRowV2Out` (template, level, band, status, office, teams, service lines, seasonal end, offshore, last sign-in, invitation expiry, `deactivated_on`), `StaffTalliesOut` (seats used, total and pending; partners, professionals, operations; SSO + MFA; active walls for `wall.list` holders only; seasonal count and earliest access end) and `PersonOut` (the drawer: the person's own `wall_ids` for `wall.list` holders, less any on a client the reader is walled from; assignment count, last three sign-ins, annual status, `version`). `PersonPatchIn`: a field sent as `null` clears it; 409 `stale_version`, `offshore_assignment_conflict`; 422 `access_ends_required`, `person_invalid`. Security role: 409 `last_admin`, `firm_role_held`. Deactivate: `manual` only from a person (422 `deactivation_reason_invalid`).
- **Roles** `RoleTemplatesOut`: templates with levels and counts, and the capability grid (`GridRowOut`: actions, cells per template, conditions, `source` matrix or policy, `locked`).
- **Annual independence** `AnnualIndependenceOut` and `AnnualConfirmIn`, which has no user id: one confirms only for oneself.
- **ADM-03** `ServiceLinePolicyOut`, `OffshoreOut` (its two toggles are always true), `FirmOfficeOut`, `FirmTeamOut`, `WallV2Out`, `WallPreviewOut`, `WallEventOut`.

## 3a. Settings keys (G-01-T04, DEC-170)
Sections `profile`, `defaults` and `plan`; a key is accepted only when registered (422 `unknown_setting`; `region` is never one). Keys today:
- `profile`: `display_name` (the portal's, required: 422 `display_name_required`), `legal_name`, `website`, `intake_mailbox`, `seatless_staff_count`, `time_zone` (`firms.time_zone`, an IANA name);
- `defaults`: `week_starts_on`, `portal_secured_footer` (the portal's; 422 `branding_not_set_up` before a display name exists);
- `plan`: `billing_contact_user_id`; `seats` (the seat total, never writable through a route; provisioning sets it, DEC-285).

At a glance rows today: `people` (`used` counting pending invitations, `pending`, `total` when seats are provisioned) and `offices_teams` (`offices`, `teams`, and `walls` only for `wall.list` holders). A row whose provider fails or takes over 500 ms is `unavailable`.

## 4. Status words
`membership`: `active` Active · `invited` Invite pending · `deactivated` Deactivated. `wall_approval`: `awaiting` Awaiting approval · `approved` Approved. `annual_independence`: `confirmed` Confirmed · `not_yet` Not yet · `declined` Declined.

## 5. Human-only actions
Every write here is a live person's; the matrix denies the agent and the system, and the services refuse non-human contexts when they go live.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | flag off; a section, person, office, team or wall the caller can't see |
| 501 | `{"detail": "not_implemented"}` | flag on, before the implementing task |
| 403 | `{"detail": "forbidden"}` | no action; stale MFA |
| 409 | `stale_version` · `last_admin` · `seats_full` · `already_member` · `firm_role_held` · `offshore_assignment_conflict` · `office_code_taken` · `one_hq` · `already_approved` · `relationship_partner` · `wall_exists` · `own_wall` | as named |
| 422 | `unknown_setting` · `display_name_required` · `audit_locked` · `access_ends_required` · `person_invalid` · `deactivation_reason_invalid` | as named |

## 7. Audit and outbox events
`firm_setting.updated` (key, never a Confidential value), `firm_setting.provisioned`, `membership.role_changed`, `membership.security_role_changed`, `membership.attributes_changed`, `membership.deactivated` (audit and outbox), `access.changed` (outbox, on every role, attribute and membership change), `wall.approved`, `independence.annual_confirmed`; per task, when live.

## 8. Example payloads
Brightwater Hale, synthetic, at E0: the overview's People row facts `{used: 46, total: 46, pending: 0}`; offices Chicago (HQ) 22, Denver 14, New York 10 seats.

## 9. Consumer contract tests
`backend/tests/contracts/firm_settings/test_firm_settings_contract.py` (G-01-T02 and T03): routes and actions, 404 and 501, no hidden or wall-derived field, registry status codes, the grid's shape, oneself-only confirmation, locked offshore toggles, agent and system denied, fresh MFA on security writes, region never writable. TypeScript fixture assertions follow with the ADM screens.

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | stub 2026-10-23 (G-01-T02); people live 2026-10-24 (G-01-T05: `StaffRowV2Out.user_id` nullable, `invitation_id`, `deactivated_on`, `StaffTalliesOut`) |
