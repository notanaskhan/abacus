---
id: TASK-992
title: S6 back-fill AC suites for TASK-041/045, TASK-030/032 and TASK-040/044, their triage, and the ADR-078 catch-up lane (Q-03-T006, T007, T008, T009, T011)
spec: SPEC-025
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-9]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T006; Q-03-T007; Q-03-T008; Q-03-T009; Q-03-T011
branch: s6-q03-backfill
test_author: ayushkbhatia
test_session: 2026-10-23, branches s6-t006-t008-backfill, s6-t007-backfill, s6-t011-catchup (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- **T006:** "Every AC of both specs has a named test_ac<N> test that passes against the migrated roles, and both task files record test_author and test_session."
- **T007:** "The suites pass against the C5 grant model and an invitation for one client never yields a grant on another client."
- **T008:** "G1-G3 are enforced on the server in every test and no gate fact is ever written by the agent principal (INV-1)."
- **T009:** "No S6 back-fill failure is open at the S7 Contract Monday and the implementing session changed no AC test." Read with the builder's triage rule: a failure is either fixed here (small, inside its module, fix and test together) or held by an `xfail(strict=True)` test recorded below and in `docs/quality/escaped-defects.md`.
- **T011:** "No amber task of the period reaches its gate without an AC suite by the other founder." Solo edition: without an independent suite written in a clean session.

SPEC-025 is the frontmatter spec (TASK-044 and TASK-045); the suites also prove SPEC-015 (TASK-030), SPEC-017 (TASK-032) and SPEC-024 (TASK-040, TASK-041).

## Plan (red)
- **Tests** in `backend/tests/integration/backfill/` over HTTP on the migrated testcontainer Postgres, headed `# ac-test-author: ayushkbhatia`, named `test_ac<N>_…`; screen-state ACs as vitest files next to the legacy screens in `apps/web/src/legacy/`.
- **Fixes** only where small and inside the AC's module, each with its test in the same commit.
- **Everything else** held by `xfail(strict=True)` with the reason and this PR's number (DEC-200), and logged in `docs/quality/escaped-defects.md`.
- **Rollback:** revert the commits; the six fixes revert with their tests.

## Results by suite

All files are in `backend/tests/integration/backfill/` unless a path says otherwise, headed `# ac-test-author: ayushkbhatia`.

### T006: TASK-041 (SPEC-024 AC-3, AC-4, AC-8) and TASK-045 (SPEC-025 AC-7)
- **AC-3, pass:** `test_staff_people.py`: the 18 tests already on main (invite, single-use hashed link, accept, email match, lockout, expiry, resend, revoke, re-invite, client contact refused, fresh MFA), plus `test_ac3_resend_ends_the_old_link_at_once` (after fix ED-004) and `test_ac3_a_security_admin_does_not_manage_people` (P-10).
- **AC-3, xfail:** `test_ac3_an_administrator_invites_a_security_admin` (ED-009).
- **AC-4, pass:** the 7 tests on main (role change and revocation apply on the next request and are audited; the last administrator is protected).
- **AC-4, xfail:** `test_ac4_a_firm_with_a_security_admin_still_lists_its_people` (500 today) and `test_ac4_an_administrator_changes_a_member_to_security_admin` (ED-009).
- **AC-8, pass:** `apps/web/src/legacy/spec024states.test.tsx`, 15 tests: People loading, error, not-allowed and empty; Autonomy loading, error and not-allowed; the checklist page (`/admin/setup`) loading, error and not-allowed (after fix ED-005); the sign-up refusal; no literal colour in any of the four screens.
- **SPEC-025 AC-7, pass:** `test_independence_gate.py`, the 11 tests on main. Nothing was missing.

### T007: TASK-030 (SPEC-015 AC-1 to AC-10) and TASK-032 (SPEC-017 AC-1 to AC-7)
`test_client_invitations.py` (35 pass, 2 xfail), `test_team_management.py` (29 pass), `apps/web/src/legacy/spec017people.test.tsx` (7 pass).
- **AC-1:** partners and managers invite with a 7-day link, audited and emitted; the response never carries the token; only the SHA-256 is at rest; a senior is refused. **xfail:** `test_ac1_the_response_carries_the_invitations_id_email_and_status` (ED-007).
- **AC-2:** a client admin invites a contributor. Inviting an admin, inviting to another client's engagement, or inviting as a contributor is refused.
- **AC-3:** an archived engagement writes no row; the 51st invitation of the day gets 409, counted per engagement. **xfail:** `test_ac3_an_archived_engagement_answers_409` (ED-008).
- **AC-4 (the row's acceptance):** one unit of work creates the user, a `client` membership without a firm role, an `owner` or `contributor` grant at `engagement` scope, the accepted invitation and the audit row. **An invitation for engagement A yields grants on A only, never on B or B's client, and reading B answers 404.** The membership is reused for a second engagement.
- **AC-5:** a wrong, expired, revoked or used token, or a different email, all get the same 404 body. Ten failures lock out that identity only.
- **AC-6:** a staff member who accepts gets 404, no grant, and stays staff.
- **AC-7:** a client lists only their engagement, and is refused firm staff, settings, team actions and another firm.
- **AC-8:** after removal or revocation the next request is refused and the grant reads `revoked`.
- **AC-9:** members and pending invitations per engagement for partners, managers and client admins; revoke and remove are audited; a client admin removes contributors, not admins.
- **AC-10:** resend issues a new link and the old one fails at once (after fix ED-001).
- **SPEC-017 AC-1 to AC-6:**
  - Candidates exclude team members, walled, revoked, client and other-firm people. A partner adds with any of the 5 roles; it is audited and only the added person is notified.
  - A manager handles senior, staff and reviewer only (403 otherwise).
  - The last partner can't be removed or demoted (409 `last_partner`); with two, one may leave (after fix ED-002).
  - A walled person added by ID gets the same 404 as an unknown one.
  - A removed member's next request is refused and their review assignment is released (`review.released`).
  - Client and other-firm users get 404.
- **SPEC-017 AC-7:** the legacy People tab is still routed: partner, manager and read-only controls; remove, role change (after fix ED-003) and Add wait for confirmation.

### T008: TASK-040 (SPEC-024 AC-1, AC-6, AC-8) and TASK-044 (SPEC-025 AC-4 to AC-7, AC-9)
`test_signup_and_engagement_types.py` (19 pass), `test_acceptance_independence_letter.py` (32 pass, 4 xfail), `apps/web/src/legacy/spec025states.test.tsx` (11 pass).
- **SPEC-024 AC-1:**
  - The firm is created with the person as its only administrator, defaults set (autonomy 1, letter policy off, default budget), the checklist with nothing done, `firm.created` audited.
  - Refused, with no firm written: a used code; the same identity again, or staff of another firm; no verified email (the code is not spent); an unknown or expired code; no sign-in.
  - The per-identity (5) and per-address (20) limits answer 409 `signup_rate_limited`.
- **SPEC-024 AC-6:** templates list their engagement types; `review`, `compilation` and `agreed_upon_procedures` engagements can be created; a matching template applies; another type's gets 409 `template_type_mismatch` and creates nothing.
- **SPEC-024 AC-8:** shared with T006 (`spec024states.test.tsx`).
- **G1–G3 on the server (the row's acceptance):** `test_ac4_g1_and_g2_are_unmet_until_the_partner_records_each_fact`. With the letter required, G3 waits for a signed letter (`sent` doesn't count), and "not required this year" with a reason meets it. **xfail:** `test_ac6_g3_is_unmet_until_the_letter_is_recorded_whatever_the_firm_policy` (ED-010).
- **INV-1 (the row's acceptance):** `authorise` refuses an agent context `engagement.acceptance.record`, `engagement.letter.record` and `independence.confirm`, even with a partner as initiator and the actions in its task scope. The database refuses `independence.confirmed` audited as the agent. **xfail:** the same for `engagement.acceptance_recorded`, `engagement.letter_recorded` and `independence.declined` (ED-011).
- **INV-5:** acceptance, letter and confirmation audit rows are `actor_kind = human`.
- **SPEC-025 AC-4:**
  - A new client's acceptance is recorded with its predecessor and conclusion, and audited.
  - Only the engagement partner may record it; firm admin, manager, senior, staff and reviewer get 403 and nothing is audited.
  - Fresh MFA is required; an empty `documented_at` gets 422; another firm gets 404.
  - A declined engagement fails G1 and invitations get 409 `acceptance_declined`; a later decision supersedes.
  - The file is stored and served as an attachment.
- **SPEC-025 AC-5:** a late joiner is asked and appears in setup and `/v1/firm/confirmations`; confirm; decline with a note only the partner and manager read; decline without a note is refused; someone off the team is refused.
- **SPEC-025 AC-6:** the partner or manager records the letter (audited as human); firm admin and senior are refused; "not required this year" needs a reason; the signed copy is stored as an attachment.
- **SPEC-025 AC-7:** `test_independence_gate.py` (T006).
- **SPEC-025 AC-9:** setup, records (after fix ED-006) and the confirmations card: loading, error, not-allowed, empty; no literal colour.

### T009: triage of every S6 failure
Every failing AC of the three suites is either fixed in this PR with its test, or held by an `xfail(strict=True)` test whose reason names this file and this PR. Each one is a row in `docs/quality/escaped-defects.md` with the layer that should have caught it. No AC test was changed to pass.

| ID | Defect | Layer | State |
|---|---|---|---|
| ED-001 | client resend left the old link working (`identity/invitations.py`) | integration | fixed |
| ED-002 | self-removal from a team answered 403 after committing (`engagements/routes.py`) | integration | fixed |
| ED-003 | legacy People role change without confirmation (`People.tsx`) | component | fixed |
| ED-004 | staff resend left the old link working (`identity/staff.py`) | integration | fixed |
| ED-005 | the checklist page drew nothing while loading, on error or when refused (`Onboarding.tsx`) | component | fixed |
| ED-006 | engagement records: 403 shown as a load error, empty independence list with no copy (`EngagementRecords.tsx`) | component | fixed |
| ED-007 | the invitation response lacks email and status (needs `make generate`) | contract | open, 1 xfail |
| ED-008 | an archived engagement answers 403, not 409 `engagement_archived` (cross-cutting `authz`) | integration | open, 1 xfail |
| ED-009 | `security_admin` missing from the `/v1/firm/staff` models, so listing answers 500 (contract change) | contract | open, 3 xfail |
| ED-010 | G3 not strict as DEC-39 (b) says (changes binder publishing and every G3 consumer) | spec | open, 1 xfail |
| ED-011 | three gate facts missing from the human-only register (register, migration, codegen) | security | open, 3 xfail |

**Next:** ED-009 and ED-011 are SEV3 and come first: ED-009 with the P-10 staff contract (the next identity contract change), ED-011 as one human-only register PR (the yaml, a migration redefining `abacus_human_only_actions()`, codegen). ED-010 needs a decision between DEC-39 (b) and SPEC-025 Q4 before any G3 consumer changes.

Spec drift is listed in `docs/quality/backfill.md` ("Spec drift found by the back-fill").

### T011: ADR-078 catch-up lane, 2027 Q1 (scoped to one session)
**Inventory** of the amber rows built so far, excluding P-06-T08 and P-01-T03/T06/T12 (PR C covers them). Every one has an independent suite on main or a later row that owes it (F-03-T34, F-03-T20, F-04-T12/T29, F-05-T22/T31/T42, P-04-T09/T12/T28, P-06-T17, Q-01-T52/T53, P-01-T15, P-08-T22, A-02-T21, K-04-T38). Three have **no owing row**:
- **F-03-T31** (TASK-389, the C1 live work-item list and `allowed_actions`): filled here by `test_f03t31_work_items_live.py`, 13 pass, no defect.
  - AC-1: five kinds with per-status counts, and the engagement and kind filters.
  - AC-2: who reads which work items (team, firm admin, no role, client user, another firm).
  - AC-3: `allowed_actions` follows the engagement role, and an action left out is refused when tried; reads write no audit event.
  - **Spec gaps:** C1 §2 does not say whether a caller without a role, or a client user, gets 403 or an empty list, so the tests accept either and assert no row or count. C1 v1 does not say whether `allowed_actions` lists reads; it lists only actions, and the test follows that.
  - Untested: the `engagements.work_items_api` flag's 404 (nothing public turns it off) and the agent principal's task scope (only a private issuer builds one).
- **F-04-T16** (TASK-392, `kernel.clock` in amber modules): not filled; owed to the next catch-up lane.
- **F-04-T27** (the WorkOS fake in TASK-996): not filled; its row's own contract tests run against it.

## Checks
- New suites: `uv run pytest tests/integration/backfill -q`, and vitest for the three `apps/web/src/legacy/spec0*.test.tsx` files.
- `make check-fast`; `uv run pytest tests/unit tests/acceptance tests/security tests/contracts -q`.

## Progress log
- 2026-10-23: suites written in three clean sessions (T006 and T008, T007, T011) and triaged. 6 defects fixed with their tests; 5 held by 9 strict xfails; all logged. The tracker moves 6 rows to back-filled.
