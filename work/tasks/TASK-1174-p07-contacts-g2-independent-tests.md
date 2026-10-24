---
id: TASK-1174
title: Independent AC tests (ADR-078) for G2 v2 and contacts and portal access live (P-07-T26)
spec: SPEC-321
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29]
risk_zone: red
status: in-progress
epic: P-07
plan_key: P-07-T26
branch: s7c-p07-contacts-live
test_author: ayushkbhatia
test_session: 2026-10-24, s7c-p07-contacts-live (before P-07-T25 is built)
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The suite is committed before T24 and T25 open for review and passes unchanged" (P-07-T26). T24
(G2 v2) is on main, so its cases pass now; T25's are strict xfails citing this task until P-07-T25
(TASK-1123) lands, and its commit removes only the markers.

## Plan (red zone)
- **File:** `backend/tests/integration/backfill/test_p07t26_contacts_g2_independent.py`, over
  HTTP through `create_app()` on the migrated Postgres (`net`, `seed`) and the published entry
  points (`identity.api`, `engagements.api`, `portal_session` as the P-08 suites use it).
- **Sources only:** SPEC-321 Story 6; P-07 Stories 2.1 and 5.2; `docs/contracts/contacts-access.md`
  §2 to §7; the matrix rows `client_access.grant`, `client_access.revoke`, `contact.unlock`,
  `contact.read`, `contact.manage`; ADR-146, ADR-164; DEC-39, DEC-226, DEC-275, DEC-277.
- **Coverage:** INV-4 (Harborline grants exactly its two delegated requests, and after acceptance
  reaches those two only); 14 days and single use; resend kills the old link; revoke keeps the
  requests and ends the session; revoke before acceptance; change scope with `seen_version`;
  unlock and its rights; the invitation email in the firm's name, one link, no amounts and no
  "Accrued"; G1 for full-client grants (intake excepted); walls 404; `scope_outside_client`;
  agent and system denied; G2 v2 view versus assign, non-attest never gated, `g2_blocks_view`
  stricter only, `client_access.grant` needs the acting member cleared on attest clients.
- **Rollback:** delete the file.

## Spec drift and gaps
- **Expired or used links:** the contract lists 409 `invitation_expired` / `invitation_used`; DEC-275
  (later, accepted) answers every acceptance failure with the same 404 so a token can't be probed.
  The suite tests DEC-275's 404 and that nothing is granted.
- **The Invitation template's key** is not named by the plan. The suite imports a platform
  default `portal.invitation` with the C16 variables `firm_name`, `recipient_first_name` and
  `app_link`; P-07-T25 records the key (DEC-301).
- **Intake grants (OQ-11)** have no scope resolver until CLI-06 (P-07-T42); that case stays a
  strict xfail citing this task after T25.

## Progress log
- 2026-10-24: suite written from the sources above before any T25 code; T24 cases pass, T25 cases
  are strict xfails citing TASK-1174.
