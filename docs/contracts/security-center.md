# Security center (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (G-02) |
| Version | v1 |
| Status | identity's routes live (G-02-T14, 2026-10-27); incidents (T18), the export schedule (T19) and safeguards (T20) still answer 501 with the flag on |
| Provider epic | G-02 (`identity` for sign-in, portal, sessions, unlock, support switch, overview and posture; `platform` for the incident read side and the safeguards program; `evidence` for the export schedule) |
| Consumers | ADM-06 (G-02-T16); ADM-01 At a glance and the M9 checklist (posture, G-01); SHL-06 (the SSO-enforced state); PLT-01 (support requests, G-04) |
| Freeze sprint | the sprint review after the stub |
| Flag | `security_center.v1` (default off, created 2026-10-26, expires 2027-04-21 under DEC-137) |
| Spec | SPEC-349 (AC-15 to AC-30, AC-45 to AC-47); G-02 §3.4 to §3.9, §4.3 |
| ADRs | ADR-020, ADR-024, ADR-031, ADR-139 (P-36), ADR-165, ADR-168; DEC-22, DEC-34, DEC-35, DEC-72, DEC-415, DEC-416, DEC-432 |

## 1. Purpose
One place where the firm's Qualified Individual runs the safeguards the FTC Safeguards Rule asks for, and the partners read them: staff sign-in (SSO, MFA, session limits, one break-glass account), the portal's sign-in floor, active sessions and staff unlocks, the incident register with its two-person decisions, the monthly firm data export and its dual approval, the support-access switch, the WISP and Pub 4557 evidence, residency, and a five-line posture.

**Stub behaviour.** With `security_center.v1` off every route below answers 404. With it on, identity's routes are live (G-02-T14: overview, sign-in, portal, SSO-exempt account, sessions, sign-out, posture, unlock, support switch); the rest answer 501 `not_implemented` until their task lands: G-02-T18 (incidents), G-02-T19 (the export schedule), G-02-T20 (safeguards).

**What Q-02 already owns, and this contract does not repeat** (`security-incidents.md`, `compliance-kernel.md` §4, `retention.md`, `legal-holds.md`): `POST /v1/firm/security/incidents` (record an incident, `incident.manage`, behind `compliance.incidents`); the on-demand firm export `GET`/`POST /v1/firm/data-exports`, `POST …/{export_id}/approve`, `/decline`, `/link` (behind `compliance.firm_export`), whose list of the last 12 (with `origin: scheduled`) is ADM-06 c's History tray; retention policies (`GET /v1/retention/policies`), read-only on ADM-06 F; legal holds. SPEC-012's `/v1/support-sessions` routes (list, approve, revoke, acknowledge) serve the support card's sessions and now admit `security_admin` (DEC-72).

## 2. Who may call it
| Operation | Method and path | Matrix action |
|---|---|---|
| Overview (sign-in, MFA, portal, residency, support switch, the viewer's actions) | `GET /v1/firm/security` | `security.read` |
| Save fieldset A | `PUT /v1/firm/security/sign-in` | `security.manage` (fresh MFA) |
| Save fieldset B | `PUT /v1/firm/security/portal-sign-in` | `security.manage` (fresh MFA) |
| Designate or clear the SSO-exempt account | `PUT /v1/firm/security/sso-exempt-account` | `security.manage` (fresh MFA) |
| Active sessions | `GET /v1/firm/security/sessions` | `security.read` |
| Sign a session out of this firm | `POST /v1/firm/security/sessions/{session_id}/sign-out` | `session.end` (fresh MFA) |
| Posture | `GET /v1/firm/security/posture` | `security.read` |
| Unlock a staff sign-in | `POST /v1/firm/staff/{user_id}/unlock` | `staff.unlock` (fresh MFA) |
| Support switch | `GET /v1/firm/support-access` | `support_session.read` |
| Change the support switch | `PUT /v1/firm/support-access` | `support_session.manage` (fresh MFA) |
| Incident register | `GET /v1/firm/security/incidents` | `incident.read` |
| Incident drawer | `GET /v1/firm/security/incidents/{incident_id}` | `incident.read` |
| Append a timeline entry | `POST /v1/firm/security/incidents/{incident_id}/timeline` | `incident.manage` |
| Decide an incident | `POST /v1/firm/security/incidents/{incident_id}/decisions` | `incident.decide` (fresh MFA) |
| Export schedule | `GET /v1/firm/data-exports/schedule` | `firm_export.read` |
| Set the export schedule | `PUT /v1/firm/data-exports/schedule` | `firm_export.schedule` (fresh MFA) |
| Approve the export schedule | `POST /v1/firm/data-exports/schedule/approve` | `firm_export.approve` (fresh MFA) |
| Safeguards record | `GET /v1/firm/safeguards` | `security.read` |
| Save the safeguards record | `PUT /v1/firm/safeguards` | `security.manage` (fresh MFA) |
| One Pub 4557 control's status | `PUT /v1/firm/safeguards/controls/{control_key}` | `security.manage` (fresh MFA) |
| Export WISP pack | `POST /v1/firm/safeguards/wisp-pack` (202) | `security.manage` (fresh MFA) |

`security.read`: `security_admin`, `firm_admin`, `quality_partner`, `practice_leader`, partners. `security.manage` and `session.end`: `security_admin` only, so every safeguards and policy edit is the QI's. `staff.unlock`: `security_admin`, `firm_admin`. `incident.read`: `security_admin`, `firm_admin`, partners; `incident.manage`: `security_admin`; `incident.decide`: `security_admin`, partners. `firm_export.read`: `firm_admin`, `security_admin`, partners; `firm_export.schedule`: `security_admin`; `firm_export.approve`: `security_admin`, partners. `support_session.read`/`.manage`: `firm_admin`, `security_admin`. Every write denies the agent and the system (INV-1, AC-45); every route answers 404 to a client principal (INV-4, AC-46).

**The matrix answers first** (security review L1): every route, the stubs included, checks the principal before it reads `security_center.v1`: a client principal gets 404; the agent, the system, a person without the action and a stale second factor get 403, whatever the flag's state.

**Read-only partners (AC-29).** Margaret Okonkwo (partner, not `security_admin`) reads everything and holds `firm_export.approve` and `incident.decide`; `GET /v1/firm/security` returns her `actions`, without `security.manage`, so the screen shows the T12 banner and locks, hides Export now and shows Approve export.

## 3. Shapes
Models in `backend/src/abacus/modules/identity/security_center_contract.py`, `backend/src/abacus/modules/platform/security_center_contract.py` and `backend/src/abacus/modules/evidence/firm_export_schedule_contract.py`; every field carries its classification. Rows carry codes and facts; the SPA composes the words ("Enforced · 46 of 46 enrolled", "Day 4 of 30 · notify by Oct 10 if ≥ 500").

- **`SecurityOverviewOut`**: `sign_in` (`SignInPolicyOut`), `mfa` (`MfaSummaryOut`), `portal` (`PortalSignInFloorOut`), `residency` (`ResidencyOut`), `support` (`SupportAccessOut`), `actions` (the viewer's allowed actions in this family).
- **`SignInPolicyOut`** (fieldset A): `identity_provider`, `sso_verified` (an admin's verified SSO sign-in exists), `require_sso`, `sso_enforced_at`, `sso_enforced_by`, `idp_mfa_attested_at`, `idp_mfa_attested_by`, `session_absolute_minutes`, `session_idle_minutes`, `platform_max_absolute_minutes` (720), `platform_max_idle_minutes` (30), `sso_exempt_account` (`person`, `factor` `hardware_key`, `last_tested_at`; who designated it and when is the audit log's), `version`. **`SignInPolicyIn`**: `require_sso`, `session_absolute_minutes`, `session_idle_minutes`, `idp_mfa_attested`, `version`; no MFA field.
- **`MfaSummaryOut`**: `enforced` and `locked` (always true, DEC-22), `enrolled`, `seats`, `idp_claim_counted` (true once "IdP enforces MFA" is recorded, R-29).
- **`PortalSignInFloorOut`** (fieldset B): `passwordless_email_code` and `passwordless_locked`, `mfa_floor` and `mfa_floor_locked` (owners, signers, approvers and anyone who can see tax return information: P-08's floor, DEC-34, DF-17), `failed_code_limit` (3) and `lockout_minutes` (15) with `lockout_locked` (DEC-35, DEC-415 Q6), `session_minutes`, `platform_max_session_minutes` (480), `version`. **`PortalSignInFloorIn`**: `session_minutes`, `version`; nothing else.
- **`ResidencyOut`** (fieldset E): `region`, `storage_primary_region`, `storage_backup_region`, `ai_inference` (`us_only`), `logs_region`, `encryption_at_rest` (`aes_256`), `encryption_in_transit` (`tls_1_3`), `locked`.
- **`SupportAccessOut`**: `allow_support_requests`, `updated_at`, `updated_by`, `version`. **`SupportAccessIn`**: `allow_support_requests`, `version`.
- **`PostureOut`**: `sso_enforced`, `mfa_enrolled`, `mfa_seats`, `residency_region`, `open_incidents`, `pub4557_open`.
- **`SecuritySessionOut`** (the sessions drawer, a P-36 page): `id`, `person`, `started_at`, `last_seen_at`, `mfa_at`, `auth_method`, `ip` and `device_label` (personal data, `confidential`), `current`. **`SessionSignedOutOut`**: `session_id`, `signed_out_at`, `signed_out_by`. **`StaffLockOut`**: `user_id`, `locked`, `unlocks_at`, `cleared`.
- **`SecurityIncidentOut`** (a register row): Q-02's entry (`id`, `ref`, `title`, `event_kind`, `discovered_at`, `consumers_affected`, `unencrypted`, `notification_event`, `ftc_notify_by`, `clock_day`, `clock_days`, `source`, `accrued_ref`, `created_at`) plus `status` (`investigating`, `closed`), `pending_decision` (`kind`, `first`, `waiting_for`, `waiting_for_seat`), `decisions` (each `kind`, `decided_by`, `seat` `partner` or `qualified_individual`, `decided_at`) and `notification_started_at`. **`SecurityIncidentDetailOut`** adds `timeline` (each `id`, `occurred_at`, `code`, `facts`, `note`, `source` `firm`/`accrued`/`system`, `author`, `recorded_at`) and `reminders_on` (the dates of days 20, 25 and 29). **`IncidentTimelineEntryIn`**: `occurred_at`, `code`, `facts`, `note`. **`IncidentDecisionIn`**: `kind` (`close_not_reportable`, `start_notification`), `second_decider_user_id` (on the first decision), `note`.
- **`FirmExportScheduleOut`**: `cadence` (`monthly`), `day_of_month` (1), `local_time` (`02:00`), `time_zone`, `contents` (`clients`, `entities`, `files`, `workpapers`, `returns`, `closes`, `audit_log`), `status` (`pending_approval`, `active`, `paused`), `approvals` (each `seat` `security_admin` or `partner` and `approved_by`; when is the audit log's), `next_run_on`, `version`. **`FirmExportScheduleIn`**: `contents`, `paused`, `version`.
- **`SafeguardsOut`** (fieldset D): `qualified_individual`, `wisp` (`name`, `format` `irs_pub_5708`, `evidence_item_id`, `approved_by`, `approved_on`), `annual_report_last_on`, `annual_report_next_due_month` (`YYYY-MM`: the handoff gives "Dec 2026"), `controls_evidenced`, `controls_total`, `open_controls` (each `control_key`, `title` from the imported definitions, `status`, `due_on`, `scheduled_on`, `evidence_item_id`), `training_completed`, `training_total`, `ptin_attested`, `ptin_total`, `access_review` (`quarter`, `due_on`, `status`), `updated_at`, `updated_by`, `version`. **`SafeguardsIn`** and **`SafeguardsControlIn`** carry the editable fields. **`WispPackOut`**: `id`, `status` (`preparing`, `ready`), `document_count`, `file_name`, `requested_by`, `requested_at`, `download_url` (Restricted, never logged), `expires_at`.

## 4. Behaviour
- **Require SSO** (AC-15): turning it on before an admin of this firm has a verified SSO sign-in answers 409 `sso_not_verified`; once on, email-code sign-in is refused with SHL-06's SSO-enforced state and ADM-07 logs "SSO enforced by ‹person›".
- **MFA** (AC-16): always enforced and locked (DEC-22); no input has a field for it, so a body that tries answers 422 before any handler. SSO users count by the IdP's MFA claim only after "IdP enforces MFA" is recorded.
- **Stricter only** (AC-17, AC-19): session limits may only be shortened below 12 hours absolute and 30 minutes idle; the portal session below 8 hours. Over a maximum answers 422 `policy_loosening_refused` with `facts.field`; under the floor (60 minutes absolute, 5 idle, 15 for the portal) 422 `session_limit_out_of_range`. The models bound nothing above, so the refusal carries its code. The BFF applies the strictest limits of the person's firms at sign-in and every refresh, counted from the session's start and last refresh, so an idle session past the firm's limit fails its next refresh and must sign in again (DEC-524). The portal session length applies to each new portal session (DEC-531).
- **Require SSO enforced** (DEC-524, DEC-535): with Require SSO on in any of the person's firms, a sign-in that is not SSO through that firm's own connection (the provider's organisation equal to the firm's `sso_connection_org`, set by provisioning) is refused (`sso_required` on SHL-06), and a live session that no longer passes ends at its next refresh. A method or organisation the provider did not report never passes. A firm without a connection cannot turn Require SSO on (409 `sso_not_verified`, `facts.reason: connection_missing`).
- **Idle time** (DEC-535): only a refresh marked `X-Abacus-Activity: user` (the person's own input) moves the idle clock; background polls never keep a session alive.
- **SSO-exempt account** (AC-18): exactly one, a current staff member; a person without a hardware-key factor (a passkey sign-in on record, DEC-525) answers 409 `sso_exempt_needs_hardware_key`; nobody designates themselves (409 `sso_exempt_not_self`, and the table's trigger); it is exempt only when it signs in with its passkey; `last_tested_at` is stamped when it signs in (`sso_exempt_account.tested`); designation and clearing are logged.
- **Portal floor** (AC-19): the passwordless code, the MFA floor and "3 codes · 15 minutes" are locked; no input has a field for them.
- **Sessions** (AC-20): only live sessions of current staff members; the IP and device are the last ones the session acted from in this firm, from this firm's own audit log (DEC-528); "Sign out of Brightwater Hale" stops the session acting in this firm (`access.changed` closes its streams and caches), its other firms unaffected (a per-firm revocation; from then on every request of that person in this firm needs the cookie of a live session not signed out of it, else 401 `session_signed_out`, and a session signed out of every firm gets no token, DEC-528); a session that is not a current member's answers 404. **Unlock**: clears the lock where the identity provider allows it (`cleared`); otherwise `locked` with `unlocks_at` ("Unlocks automatically at 9:39 AM", DEC-35; SPEC-349 Q7). No adapter in the repository reads or clears a staff lock yet (DEC-526), so the answer is `locked: false, cleared: false` until the WorkOS staff adapter lands.
- **Incidents** (AC-21 to AC-23): the clock is Q-02's on `kernel.clock`. A decision needs one partner and the QI, distinct, each with a fresh second factor: the first decider names the other and the incident reads "Waiting for ‹name›"; the named person's same decision completes it (`close_not_reportable` closes it; `start_notification` starts the notification). The same person twice, the same seat twice or anyone not named answers 409 `decider_must_differ`; a decided incident answers 409 `already_decided`. Timeline entries are append-only and attributed; an Accrued entry (RB-27) has `source: accrued`. Reminders reach the QI and the partners on days 20, 25 and 29.
- **Export schedule** (AC-25): runs only once a `security_admin` and a partner have each approved it, two distinct people (DEC-72); any change takes it back to `pending_approval`; a repeat approval by the same person or for a seat already filled answers 409 `approver_must_differ`. Each run notifies both. The on-demand export and its approval are Q-02's (AC-24).
- **Safeguards** (AC-27): the QI edits; "Export WISP pack" answers 202 and prepares one zip of the WISP and its linked evidence ("WISP evidence pack prepared · 14 documents").
- **Support switch** (AC-28): off, a new support-session request (`POST /v1/support/sessions`) answers 409 `support_requests_disabled`, pending requests are closed, and no approval (firm or emergency) grants one; sessions already granted keep their expiry. A pending request is approved or declined by `firm_admin` or `security_admin` with a fresh second factor; a granted session reads "Granted until ‹time›" and can be revoked (SPEC-012).
- **Residency and retention** (AC-26): residency is locked and comes from `firms.region` and settings; retention is read here, never written (FIL-02 owns it).
- **Posture** (AC-30): the five facts agree with the fieldsets and feed ADM-01 and the M9 checklist. Open incidents come from the register (platform registers the count); Pub 4557 items count 0 until T20 registers the safeguards record.
- **MFA summary** (AC-16): `enrolled` counts current staff with a second-factor sign-in on record (every staff session needs one); `identity_provider` stays null until the WorkOS staff adapter reports the connection (DEC-527).
- **Purge**: staff sessions that ended (or expired) more than a year ago are deleted daily (`auth_session_purge:platform`).
- **Optimistic concurrency**: every save carries the `version` it read; a stale one answers 409 `stale_version`.

## 5. Audit events
`security_policy.updated`, `security_policy.sso_enforced`, `security_policy.idp_mfa_attested`, `portal_security_policy.updated`, `sso_exempt_account.designated`, `sso_exempt_account.cleared`, `sso_exempt_account.tested`, `session.signed_out`, `staff.unlocked`, `support_access.updated`, `incident.timeline_appended`, `incident.decision_recorded`, `incident.decided`, `firm_export_schedule.updated`, `firm_export_schedule.approved`, `safeguards.updated`, `safeguards_control.updated`, `wisp_pack.prepared`. Each names the person; scheduled runs are "System" (AC-47).

## 6. Errors
404 (flag off; a client principal; another firm's or an unknown incident, session or person), 403 (no matrix right; a stale second factor), 401 `session_signed_out` (any route, for a session signed out of this firm), 409 `sso_not_verified`, `sso_exempt_needs_hardware_key`, `sso_exempt_not_self`, `decider_must_differ`, `already_decided`, `approver_must_differ`, `support_requests_disabled`, `stale_version`, 422 `policy_loosening_refused`, `session_limit_out_of_range` and request validation, 501 while stubbed.

## 7. Consumer tests
`backend/tests/contracts/security_center/test_security_center_contract.py` (this stub); `backend/tests/integration/test_g02t12_security_center_ac_suite.py` (AC-15 to AC-30, independent, G-02-T12). Fixture mode serves ADM-06 a to h, the sessions and unlock states and the support states (`apps/web/src/fixtures/scenarios/ADM-06.ts`).

## 8. Change log
- v1 (2026-10-26, G-02-T11): stub. DEC-432 records the module placement and the shape choices.
- v1.2 (2026-10-27, G-02-T14 security review): SSO through the firm's own connection, cookie-bound requests after a per-firm sign-out, the activity mark, pending support requests closed with the switch (DEC-535).
- v1.1 (2026-10-27, G-02-T14): identity's routes live; `session_limit_out_of_range`, `sso_exempt_not_self` and the 401 `session_signed_out` added; DEC-524 to DEC-531.
