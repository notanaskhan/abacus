---
id: TASK-8083
title: "A-08-T15: Link principals (red): migration 0893, authenticator, page credential, email OTP"
spec: SPEC-657
acceptance_criteria: [AC-6, AC-7]
risk_zone: red
status: in-review
branch: a08-t15-link-principals
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T15
---

## Objective
The identity a public confirmation page acts as: minted for one purpose, subject and address;
resolved only through SECURITY DEFINER functions; email codes (10 minutes, five wrong lock 15
minutes); a `__Host-` page credential with CSRF; uniform padded answers; the platform kill switch.

## Plan (red: written before the build)
1. Migration **0893** `link_principals`: `link_principals`, `link_principal_challenges`,
   `link_page_credentials` (RLS not FORCEd so the owner's definers resolve before any tenant is
   known; the app role stays bound by the policy and has no direct access to challenges or
   credentials); seven definers.
2. `identity/link_principals.py` (+ `identity.api`): `register_link_purpose`, `mint_link`,
   `revoke_link`, `resolve_link`, `request_code`, `issue_link_code`, `verify_code`,
   `credential_principal`; event `link_principal.code_requested`.
3. `communications/link_codes.py`: delivery from the DB template `confirmation.respond_code`.
4. `assurance/confirmations_contract.py`: the public family resolves real links (fixtures stay
   for local and test); verify sets the cookie and returns the CSRF header.
5. Tests: `tests/integration/test_a08t15_link_principals.py`, `tests/unit/assurance/test_a08t15_confirm_routes.py`.
Rollback: revert; downgrade drops the tables and functions; the `confirmation_links` control
(P-66) turns every link off at once.

## Progress log
- `2026-11-15` — Built (DEC-5065). Route test passes locally; the Postgres tests run at the end
  pass. Human: import the `confirmation.respond_code` template per environment before links go out.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5065 | Definers past RLS (NO FORCE) on the link tables; sealed address for delivery; five-try lock | no |
