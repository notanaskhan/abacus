---
id: TASK-1269
title: Independent AC suite for offices, teams and groups, walls v2, offshore, service lines, the access-end job and annual independence (G-01-T15; for G-01-T08, T09, T12, T13)
spec: SPEC-002
acceptance_criteria: [AC-12, AC-13, AC-14, AC-15, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24]
risk_zone: red
status: in-review
epic: G-01
plan_key: G-01-T15
branch: s9a-identity-access
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9a-identity-access (one clean session, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
- **G-01-T15:** "The suite passes on T08, T09, T12 and T13 with no edits by N." Office and team rules, the DEC-30 property, walls v2 (INV-3, DEC-43, DEC-73), offshore fail-closed (I-OFFSHORE as amended by TASK-1207), service lines, access-end job idempotence, self-only confirmation, agent and system refused.

## Plan (red zone)
- **Files (tests only):** `backend/tests/integration/backfill/test_g01t15_org_walls_offshore_independent.py` (G-01-T08, T09) and `backend/tests/integration/backfill/test_g01t15_service_lines_independence_independent.py` (G-01-T12, T13).
- **Sources of expectations:** G-01 §3.4 AC4.5, §3.6, §3.7, §3.8, §3.9 (amended), §3.10, §3.11 AC11.2, §4.3; SPEC-002 Stories 2, 3, 5, 6; SPEC-024 AC-9 to AC-12; `docs/contracts/firm-settings.md`; the identity and organisations matrices; DEC-30, DEC-43, DEC-73, DEC-317, DEC-318, DEC-319 (TASK-1207), DEC-380, DEC-381. Implementation files were not read to decide an expectation; route declarations, `api.py` signatures and the Pydantic contract models were read to learn how to call things.
- **Production:** none. No migration, route, matrix, flag or registry change. No xfail markers (per the parent session's brief, failures are reported as defects instead).
- **Rollback:** delete the two files and this task file.

## Results
Command (from `backend/`): `uv run pytest tests/integration/backfill/test_g01t15_org_walls_offshore_independent.py tests/integration/backfill/test_g01t15_service_lines_independence_independent.py -q -p no:cacheprovider -n 2` → 67 passed, 2 failed (71.7 s).

- **`test_g01t15_org_walls_offshore_independent.py` (43 tests: 41 pass, 2 fail).**
  - Offices (AC7.1, AC7.2; DEC-317): codes unique per firm and free across firms, the `^[A-Z]{2,6}$` shape, one HQ on create, on PATCH and in the database, IANA time zones, seats derived from active memberships, lead and address, PATCH needs `version` (422) and a stale one is 409, `office.created`/`office.updated` as Grace, who reads and who manages (security admin manages, partner reads only, staff refused, stale MFA 403), another firm's office and team 404 and never listed, another firm's person never joins a team.
  - DEC-30: `authorise` decisions over seven principals (firm admin, practice leader, quality partner, security admin, partner, seasonal, staff) × firm and two engagements × a reproducible sample of matrix actions plus every new write, and every principal's `GET /v1/engagements`, are unchanged while every office value moves (memberships, engagements, leads, HQ) over two rounds; no matrix rule names an office.
  - Teams (AC7.3, AC7.4; DEC-317): a `service_line` team names its line and only it does, the dropped `offshore`/`wall_group` kinds are 422, `team_name_taken`, joining and leaving moves `memberships.service_lines` with audit and `access.changed`, rosters are insert-only history, a property test over 14 reproducible roster changes on four teams, a person edit asking for a team-managed line is 422 `person_invalid`, a security admin cannot change who holds a line, the Seasonal date sets every active seasonal member with one audit row each.
  - Walls v2 (AC8.1 to AC8.7; SPEC-002 AC-4 to AC-10, AC-12 to AC-17): active at once and awaiting Margaret, `wall.created` names the approver with identifier-only payload, `access.changed`; from the next request (before any consumer) Ashford's engagement, request items, team and work items answer exactly the unknown-id 404 and the list drops it with no hidden field while Ridgeline stays; a later engagement is walled too; an agent acting for Lena is refused on Ashford and not on Ridgeline; staff, security admin and stale MFA refused; reason vocabulary and 500-character text; `approver_not_partner` for staff, a firm admin, a revoked partner, the walled person and the creator; Neil Ashcroft blocker and 409 `relationship_partner`; `wall_exists`; the preview counts that client's assignments only and answers 404 for an unknown or other-firm client or person and for a creator walled from the client; only the named partner approves, with fresh MFA, once (`not_named_approver`, `already_approved`), forward-only in the database, a lifted wall 404; partner-only lift with fresh MFA, firm admin 403, `own_wall`, history kept; the register for admins, security admins and partners (less their own and hidden clients); the log newest first, 404 for a hidden client, another firm's wall 404; At a glance's wall count only for `wall.list` holders; the consumer ends Ashford only, as the system on behalf of Grace, idempotently.
  - Offshore (AC9.1 to AC9.4, AC4.6; SPEC-002 AC-18 to AC-20; DEC-319): ADM-03d lists Remy with 0 consented clients and both toggles locked on, no API turns them off; Remy reads and lists by role (not a wall) and a wall still binds him; 409 `offshore_consent_required` on a team add while an onshore colleague is added; 409 `offshore_assignment_conflict` and nothing changes; 403 `own_offshore`; the TIN reaches an offshore partner masked, no reveal is offered, the reveal is 403 and `authorise` refuses `tin.reveal`.
  - INV-1: agent and system denied and refused on `org_structure.manage`, `firm.manage_users`, `wall.create`, `wall.approve`, `wall.remove`.
- **`test_g01t15_service_lines_independence_independent.py` (26 tests: 26 pass).**
  - Service lines (SPEC-002 AC-21 to AC-24; AC10.1 to AC10.3; DEC-380): four lines in order at version 0 "Engagement team only"/"Hand-offs only"; Audit locked in the API (422 `audit_locked`) and the database CHECK; partner and staff refused, stale MFA 403, security admin allowed, 409 `stale_version`, `service_line_policy.updated` as the person and `service_line_policy.changed`, `service_line_lead_invalid`; opening Tax lets Kevin read the engagement and its request items and list it, not CAS, not for a CAS member, with `access.changed` only for Tax holders, and narrowing ends it on the next request; the reach never grants `request_item.mark_ready`, `request_item.send` or `comment.share` (a teammate holds them); never Audit, never an attest client; never a walled client, an offshore member, level `admin`, or content for a firm or security admin; lists agree with `authorise` for five principals over five engagements; another firm's policy reaches nothing here.
  - Annual independence (AC6.1 to AC6.3; SPEC-024 AC-10 to AC-12; DEC-381): 409 `independence_statement_missing` before a statement, statement publish needs fresh MFA, one's own status, a confirmation for oneself only with the version read, insert-only row with `actor_kind = 'human'`, audit and outbox, `has_current_annual_confirmation`; a body naming another user is 422 and writes nothing; a decline needs a note, other years 422 `annual_confirmation_invalid`, the newest answer wins; a newer statement makes the old version 409 `stale_version`; the app role holds no UPDATE or DELETE and the CHECK refuses an agent row; a client user is refused and the matrix denies agent, system and client roles; the year's list for firm admin, partner and quality partner foots to its rows with notes and dates, 404 for staff and security admin; another firm reads and counts nothing.
  - Access-end job (AC4.5; SPEC-024 AC-9; DEC-381): still active at 23:50 CT on the last day; at Nov 1 00:20 CT the five end with `access_ended` as the system on behalf of Grace, five `membership.deactivated` (audit and outbox), `access.changed`, five seats freed, "Deactivated" and `deactivated_on` Oct 31 on ADM-02e; re-runs change nothing; a date Ada moved is respected and its end names Ada; the firm's own time zone decides the day (Los Angeles vs Chicago); one T-7 notice per date (and a second date its own); the last firm and security admins are never ended; another firm is untouched.
  - INV-1: agent and system denied and refused on `service_line_policy.manage`, `independence.annual_confirm`, `firm.manage_settings`, `firm.manage_users`; `independence.annual_read` denies both.

## Defects found (tests kept as the spec says; no xfail)
1. **`PUT /v1/firm/teams/{id}/members` with the roster the team already has answers 500** (`MissingAuditEvent`). `test_ac7_3_putting_the_same_roster_again_changes_nothing_and_answers_200`. Spec: G-01 §4.3 (`PUT /{id}/members` sets the roster) and `FirmTeamMembersIn` "The whole roster"; an unchanged roster is a no-op that must answer 200, not an internal error. Observed: the second identical PUT (service-line team and, by the same path, any team) raises `MissingAuditEvent` in the unit of work and the API answers `{"detail":"internal error"}`. Owner: G-01-T08 (`organisations` rosters).
2. **`GET /v1/walls` items carry no `allowed_actions`.** `test_ac11_2_a_partner_sees_approve_only_where_named_and_lift_except_their_own`. Spec: the contract §1 ("each `WallOut` carries `WallV2Out`'s fields beside SPEC-002's"; `WallV2Out` has `allowed_actions`), G-01 AC11.1 (visibility from `allowed_actions`) and AC11.2 (per-row Approve and Lift only where Daniel is the named approver or a partner). Observed: `WallOut` has the v2 data fields but not `allowed_actions`, so the register cannot say per row who may approve or lift. Owner: G-01-T09 (identity `routes.py` `WallOut`); a contract-shape change, so it needs `make generate`.

## Spec gaps (no defect)
- The epic names `office.read/manage` and `team.read/manage`; the contract §2 fixes one pair, `org_structure.read/manage`, followed here.
- `POST /v1/firm/offices` and `POST /v1/firm/teams` status codes are not fixed (200 or 201 accepted). Who may read the offices list beyond `org_structure.read` holders is matrix-only; staff are asserted refused (403 or 404).
- The service-lines GET for a staff member: the contract's 404 row covers "a section … the caller can't see" and 403 "no action"; either is accepted.
- AC4.5's "Deactivated Oct 31" is read as `StaffRowV2Out.deactivated_on` = the last day of access (passes today); the contract does not define the field's date further.
- SPEC-002 AC-15 says "anyone else gets 403"; for a wall with no named approver (DEC-318's legacy case) every partner gets 403, asserted without a code.
- `GET /v1/walls/{id}/events` for a staff member: matrix 403 or not-found 404 is not fixed; either accepted. An admin of another firm gets 403 or 404 on the wall routes (no `wall.*` cell of theirs reaches it); partners of another firm 404.
- DEC-381's notice audience (firm admins) is read from the outbox and audit row counts; the C16 notification rows are written by the relay consumer, which these tests do not run.

## Not tested (and why)
- AC8.2's `wall_approval_requested`/`wall_approved` notifications and email: relay consumers (notifications module), not run in this boundary; the outbox events are asserted.
- AC7.1's 340 ms expand animation, AC8.6's tint: frontend (G-01-T14/T16).
- AC9.4's generated `test_tri_and_offshore.py` cases: owned by `tests/security`, not re-implemented.
- AC10.4 fallback (`SERVICE_LINE_REACH` False): a code constant; flipping it would edit production code.

## Progress log
- 2026-10-26: both suites written from the specs, contracts and decisions only; targeted runs with `-n 2` (sorted files); `ruff format`, `ruff check`, `pyright` on the two files and `banned_patterns` pass. Two defects reported above for the implementing session; no production code, migration or existing test edited; nothing committed.
- 2026-10-26 (parent session): both defects fixed in production code, the suite unchanged: ED-070 (`set_team_members` no-op roster rolls back and answers 200) and ED-071 (`WallOut.allowed_actions`, generated client regenerated; SPEC-002's pinned wall keys gained the field). Re-run with the walls, org and contract suites: the two suites 69 pass.
