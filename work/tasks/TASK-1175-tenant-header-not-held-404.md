---
id: TASK-1175
title: A tenant header naming a firm the person does not hold answers 404, real or not (ED-024, Q-03-T016)
spec: SPEC-000
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T016
branch: s7c-tenant-404
created: 2026-10-24
updated: 2026-10-24
---

## Objective
SPEC-000 AC-1 to AC-3 (tenant from the membership; no membership is 403; revoked is denied), as
P-01 AC 2.1.4 refines them: "Given a tenant id she does not hold, then the API answers 404". Today
`current_context` answers 403 `forbidden` (ED-024). A real firm the person is not in and a firm
id that never existed must answer exactly alike: status, body, headers and the same code path
(no lookup of the named firm), so nothing tells them apart.

## Plan (red zone)
- **One place:** tenant resolution. `identity/context.py` gains `TenantNotHeld(NoActiveTenant)`;
  `identity/service.py` `choose_tenant` raises it when a person with at least one active
  membership names, in a well-formed `X-Abacus-Tenant`, a tenant that is none of them (never
  read the firm, so both cases take the same path);
  `identity/routing.py` `current_context` maps it to `NotFound`, which the app renders as every
  other 404 (`{"detail": "not found"}`). No per-route change.
- **Unchanged:** no membership at all (403 whatever the header names, SPEC-000 AC-2); no header (one membership: that firm; several: 403); a malformed header
  (not a tenant id: 403); an unknown user (403); the support path (`X-Support-Session`, its own
  firm check); portal sessions (host-pinned, ADR-168: 401 on a mismatched header); staff tokens
  (`STAFF` routes never read the header); `/v1/me` (`SELF`, reads the header itself). There is
  no audit of a refused tenant switch today, so none to keep.
- **Decision:** DEC-304 records that P-01 AC 2.1.4 supersedes TASK-007 contract §4 step 4 for a
  header naming a tenant the person does not hold (a revoked membership included: it is not held).
- **Tests:** unit `tests/unit/identity/test_tenant_choice.py` (choose_tenant's outcomes);
  security `tests/security/test_tenant_header_not_held.py` (route-table sweep: every firm route,
  non-member vs never-existed, same status, body and headers, 404, with a control); remove the
  strict xfail on `test_ac214_the_tenant_comes_from_a_held_membership_never_the_header_alone`
  (assertion unchanged); move foreign-tenant 403 assertions to 404 where the spec requires.
- **Migration:** none. **Flags:** none (a status change on a refusal; nothing to roll out).
- **Rollback:** revert the commit.

## Progress log
- 2026-10-24: red first: `tests/unit/identity/test_tenant_choice.py` (import error: no `TenantNotHeld`) and `tests/security/test_tenant_header_not_held.py` (3 failed, 403 not 404). Fixed in `choose_tenant` / `current_context` only; both green. The P-01-T15 strict xfail is removed, its assertion unchanged (9 pass). A first cut also sent a person with no membership at all to 404, which broke SPEC-000 AC-2 ("the response is 403"); narrowed to members (the rule still reads only her own memberships, so no firm is told from another).
- 2026-10-24: foreign-tenant 403s moved to 404 (spec line in DEC-304): `test_identity.py` `test_ac1_a_header_naming_a_firm_the_user_does_not_belong_to_is_404`, `test_ac1_a_header_naming_a_tenant_that_does_not_exist_is_404`, `test_ac1_a_header_naming_a_revoked_membership_is_404`, `test_ac1_a_user_in_another_firm_cannot_borrow_this_firms_tenant_id`, `test_ac3_revoking_one_of_two_memberships_removes_only_that_tenant` (the revoked-firm call only); `test_tenancy_escape.py` `test_adr014_a_header_naming_another_firm_gives_nothing_to_a_non_member`. No other assertion changed.
- 2026-10-24: done. `tests/unit tests/contracts tests/security`: 28131 passed, 14 xfailed. Integration (P-01-T15, identity, staff session, portal sign-in x3, security incidents, tenant provisioning, telemetry tunnel x2, F-03 independent, model foundation journey, review undo, engagements, retrieval API, TIN reveal, evidence, firm settings live, retrieval, agent walls x3, all of `backfill/`): 1293 passed, 10 xfailed. `make check-fast` green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-304 | TASK-007's 403 for an unheld tenant header vs P-01 AC 2.1.4's 404 | No (ADR-002 unchanged) |
