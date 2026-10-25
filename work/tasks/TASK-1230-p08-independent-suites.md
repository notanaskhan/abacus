---
id: TASK-1230
title: Independent AC suites for the portal home, sign-in hardening and the portal security files (P-08-T22, P-08-T24, P-08-T25)
spec: SPEC-320
acceptance_criteria: [AC-9, AC-15, AC-16]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T22; P-08-T24; P-08-T25
branch: s8b-accept-tests
test_author: ayushkbhatia
test_session: 2026-10-25, branch s8b-accept-tests (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-25
updated: 2026-10-25
---

## Objective
- **P-08-T22:** "The suite ... passes on main, including a planted firm status code that the DTO test rejects."
- **P-08-T24:** "The suite passes on main from the SPEC and contract alone, with allow and deny cases for every client role in the MFA floor."
- **P-08-T25:** "Both files are required checks before pen test #1 ... and fail on a planted cross-scope read."

## Plan (red zone)
- **Files (tests only):** `backend/tests/security/test_portal_scope_isolation.py`, `test_portal_host_pinning.py` (T25); `backend/tests/integration/backfill/test_p08t24_portal_mfa_invitations_recovery.py` (T24); `backend/tests/integration/backfill/test_p08t22_portal_home.py`, `backend/tests/integration/test_p08t22_portal_seed_footing.py`, `backend/tests/unit/portal/test_p08t22_stages_independent.py`, `apps/web/src/entries/portal.p08t22.test.ts` (T22).
- **Production:** `requests/service.py` `your_part` (ED-054). No migration, route, matrix or flag change.
- **Rollback:** revert the commit.

## Results
- **P-08-T24 (38 pass):** the MFA floor for all 12 grant roles and 6 designations, allow and deny each; fail-closed on a raising or stalling predicate; stricter-only extension; backup codes single use; trusted-device expiry, fewer days, reset revokes; invitation preview's single 404 (no oracle), single use, 14 days; grants attributed to the inviter (INV-5); renew to the original address only; agent refused unlock and reset (INV-1); pause within 10 s.
- **P-08-T25:** role union (Meera Shah), request-scoped third party (Sam Ortiz), owner versus contributor, cross-tenant host swap, a firm session on a portal host and the reverse; each file has a test proving its probe fails on a planted cross-scope read.
- **P-08-T22:** CSP as the portal build injects it and the portal entry's import graph (vitest, 8); stage exhaustiveness over every stored registry code (122); home `scope_only` per target scope, counts tie to `your-part`, no firm status, amount or agent field with a planted firm status the DTO test rejects, preferences per scope; footing of the portal seed slice.

## Escaped defects
- **ED-054 (fixed):** `requests/service.py` `your_part` returned before authorising for a caller with no client role, so `GET …/request-items/your-part` on an engagement the client's grants don't cover answered 500 (`authz.unchecked_route`), not 404 (SPEC-320 AC-16, DEC-43); and it counted a draft binder's requests the home leaves out, so the two no longer tied (DEC-210) and a draft reached the client's count. It now authorises `request_item.read` first and counts the home's own rows (`client_home_items`: published or done binders). `test_inv4_your_part_of_an_uncovered_engagement_is_refused_not_an_error`, `test_ac15_a_draft_binders_requests_count_nowhere_for_the_client`.

## Held open (strict xfail; known, not escaped)
- **Staff token on a portal host** is served as the staff session (`/v1/me` 200) instead of refused as no session (ADR-163 §5, ADR-168, SPEC-320 AC-9). DEC-212 gives the refusal to P-08-T25; the fix is in identity authentication, outside an independent-test row's fix scope. `test_portal_host_pinning.py`.
- **`/v1/me` answers 401 to a portal session** on its own host (contract §2.1, §3 `MePortalOut`; DEC-212 "not yet", owed by P-08-T07). `test_p08t22_portal_home.py`.
- **Meera's `taxpayer` work-item grant holds no engagement role**, so her 1040 home answers 404 (Story 6.5, AC-15; open in DEC-213, identity's role derivation). `test_portal_scope_isolation.py`.
- **The portal slice seeds no TOTP factor for Tess Moreno** (P-08-T14; DEC-213's wait on P-08-T17's tables, which have now landed). `test_p08t22_portal_seed_footing.py`.

## Spec gaps (DEC candidates, not decided here)
- The Feld binder reads "19 of 21 · 37 sorted" in POR-02a and SPEC-320 AC-15 but "5 of 7" in BND-02a and P-06's goldens; only "Upload 2" and its footing, on which both agree, are asserted.
- The registry's derived chips (`close.past_due`, `audit_engagement.processing`) raise `UnknownStatus` in the stage projection; "every registry code" is read as every stored code.
- The portal CSP allows `img-src 'self' data:`; ADR-163 says `img-src 'self'`.
- An audit work item at `planning` shows the pill "We're finishing your audit".

## Outside these rows (reported, not tested here)
- `GET /v1/portal/binders` answers 500 (`authz.unchecked_route`) for a client with an engagement grant (R-01).
- Assigning a request to someone with only an entity-level grant hits a foreign-key error ("client assignee holds no grant").
- Read while fixing ED-054, not yet tested: the legacy `GET /v1/engagements/{id}/request-items` query (`repository.list_request_items`) filters a client's rows by `client_visible` but not by binder status, so a client may list a draft binder's requests there; existing back-fill fixtures seed client reads into the site's draft binder, so the fix needs those fixtures moved first.

## Progress log
- 2026-10-25: three suites written from SPEC-320, the portal contracts and the decisions; ED-054 fixed; four known gaps held as strict xfails citing their decisions. One integration run in four showed a single failure that three clean reruns did not reproduce (suspected the 10 s pause test under load); not confirmed.
