---
id: RB-37
title: Onboard a firm's people, offices and walls
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-03-16
---
# RB-37 · Onboard a firm's people, offices and walls

Owner: firm-admin desk (AY lane) · Applies to: a new firm's first week · Contract: `docs/contracts/firm-settings.md` (v1, frozen 2026-10-28) · Screens: ADM-01, ADM-02, ADM-03 · Task: G-01-T18

Use only this runbook and the contract. Every write below needs a **fresh second factor** (the contract's "fresh MFA"), is a person's act (the agent and the system are refused), and is audited. Do the steps in order: later steps check facts the earlier ones set.

## 0. Before you start

- [ ] The firm exists, with its firm admin signed in. Their `GET /v1/firm/settings/overview` answers 200.
- [ ] You hold the people list in the firm's own format: name, work email, level (partner, manager, senior, staff), firm role if any (firm admin, practice leader, quality partner), office, team, service line, and whether the person is offshore or seasonal.
- [ ] Offshore preconditions are written down **before** anyone offshore is invited (section 4).
- [ ] Synthetic data only on a rehearsal firm. Never paste a real person's details into a ticket, a commit or this runbook.

## 1. Offices, then teams

1. Create each office: `POST /v1/firm/offices` (`org_structure.manage`). Offices are a **filter, never an access boundary** (DEC-30): no permission reads an office.
2. Create each team: `POST /v1/firm/teams` with its `service_line`, then `PUT /v1/firm/teams/{team_id}/members` once people exist (step 2).
3. Check: `GET /v1/firm/offices` and `GET /v1/firm/teams` list them, each with `version` 1.

## 2. People

1. Invite each person: `POST /v1/firm/staff/invitations` (`firm.manage_users`), one per email, with level and office. A person appears in `GET /v1/firm/staff` as invited (`invitation_id` set, `user_id` null) until they accept.
2. Firm roles: `PUT /v1/firm/staff/{user_id}/role` after they accept. Security roles: `PUT /v1/firm/staff/{user_id}/security-role` (`security_role.assign`, a security admin's act).
3. Resend or revoke an invitation: `POST /v1/firm/staff/invitations/{invitation_id}/resend` or `/revoke`.
4. Seasonal people: set their access end with `PUT /v1/firm/groups/seasonal/access-ends`. Access ends by itself at that date (the hourly sweep, G-01-T13); the person gets a seven-day notice.
5. Check: `GET /v1/firm/staff` tallies (`StaffTalliesOut`) match your list. For a 46-person firm: 46 rows, each either active or invited, none unexpected.

## 3. Service lines and annual independence

1. Service-line separation: `PUT /v1/firm/service-lines/{line}` (`service_line_policy.manage`; firm admins and partners, never security admins, ADR-183).
2. The firm's annual independence statement: `PUT /v1/firm/independence/statement`. Each person confirms their own (`POST /v1/me/independence/annual`); `GET /v1/firm/independence/annual?year=` shows who has not.

## 4. Offshore

Preconditions (DEC-52; ADR-024), all true **before** an offshore person is invited:

- [ ] The firm has a written client consent basis for offshore access (§7216 where tax data is involved).
- [ ] The offshore group is set up: `GET /v1/firm/offshore` shows it.
- [ ] The person's membership will be in the offshore group from their first sign-in. Offshore readers see TINs and Restricted fields masked everywhere (AC9.4); there is no per-screen exception.

## 5. Walls

A wall keeps one person away from one client, with **404 semantics**: the walled person sees nothing of the client, not even a count (DEC-43).

1. Preview: `GET /v1/walls/preview?user_id=&client_id=` shows what the wall would end (assignments, open work). Read it before you create.
2. Create: `POST /v1/walls` (`wall.create`; firm admins and partners). A wall waits for its named partner.
3. Approve: the **named partner** approves with `POST /v1/walls/{wall_id}/approve` (`wall.approve`, fresh MFA). Nobody else can, and never the person who created it.
4. History: `GET /v1/walls/{wall_id}/events`. Remove only with `POST /v1/walls/{wall_id}/remove` and a reason.
5. Check: sign in as the walled person (on a rehearsal firm) and confirm the client is absent from Clients, Engagements, Home and search, with no "hidden" note anywhere.

## 6. Done

- [ ] Offices, teams, people and walls match the firm's list.
- [ ] Every invited person has accepted, or has a resend logged.
- [ ] Offshore preconditions are recorded in the firm's onboarding ticket.
- [ ] The audit trail shows each step as the person who did it (`GET /v1/audit` filtered to the firm admin).

If any check fails, stop and raise it in the firm's onboarding ticket; do not work around a refusal (a 403 or 404 is the product doing its job).
