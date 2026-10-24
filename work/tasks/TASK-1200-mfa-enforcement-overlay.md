---
id: TASK-1200
title: MFA enforcement overlay - the fresh-MFA lint and the generated overlay test over authorise and the route table (Q-02-T37)
spec: SPEC-050
acceptance_criteria: [AC-17]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T37
branch: s8a-identity-security
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Removing mfa_recent from a listed action fails CI" (Q-02-T37; Q-02 AC-42). Scope for S8 wave A (the coordinator's brief): a lint plus a generated test that every action in `docs/architecture/fresh-mfa-actions.yaml` has `mfa_recent: required` and is enforced on its route. (SPEC-050 is named only because the task schema needs a spec; Q-02's own SPEC is not written.)

## Plan (red zone: authorisation tests and tooling)
- **Lint:** `abacus_tools.quality.fresh_mfa` reads the register and the matrix *sources* (`permission-matrix/*.yaml`, through `codegen.permission_matrix.source`), so a removed condition fails before regeneration; added to `make check-fast`. Tests: `tests/unit/quality/test_fresh_mfa_lint.py` (seeded violations).
- **Generated overlay:** `abacus_tools.codegen.security_tests` renders `tests/security/test_fresh_mfa_generated.py` (in `make regenerate` and `check-generated`): one case per listed action with a role its row allows (conditions cleared, so the case isolates the MFA attribute; `firm_partner` for `wall.approve`); `authorise` allows with a factor verified a minute ago and refuses just over 15 minutes and never (`matrix_harness.mfa_outcome`); and the table of routes declaring a listed action, checked against the app (an `AbacusRoute` answers only after its declared action was authorised, so a route declaring the action enforces the MFA rule).
- **Register:** `contact.mfa_reset` joins `portal_access` (P-08-T21 serves it).
- **Rollback:** revert the commit.

## Progress log
- 2026-10-25: built. `test_fresh_mfa_generated.py` 77 cases, `test_fresh_mfa_lint.py` 5, `test_fresh_mfa_actions.py` 22.
- **Deferred (the rest of the row, not in this wave's brief):** the staff-route test that a session without a verified second factor (WorkOS `amr`) is refused (AC-43 first half: today `mfa_at` is only the fresh-MFA input, and refusing every staff route without `amr: mfa` changes sign-in for every firm; it waits for WorkOS MFA to be on in each environment, before M7, Fri Apr 16); the Safeguards floor for deliverable scopes (no deliverable grant kind exists; signing and approving are P-08-T17's `engagement_designation` predicate, owners its `owner_grant`); `make mfa-report`. Five listed actions have no route yet (`export.create`, `firm_export.*`: G-02 and Q-02-T43), so they are enforced wherever a service authorises them and show in the generated table when their routes land.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-330 | The overlay as built; the rest of T37 deferred | No |
