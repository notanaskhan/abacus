---
id: TASK-1333
title: Independent AC suite 2 (ADR-078) for the security center against the stubs
spec: SPEC-349
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-45, AC-46, AC-47]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T12
branch: s10b-audit-trail-export
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The ADM-06 acceptance tests, written before the implementations (G-02-T14 sign-in, sessions,
unlock and support switch; T18 incidents; T19 export schedule; T20 safeguards; Q-02-T43 the
on-demand export), from SPEC-349 §5.4–5.9 and `docs/contracts/security-center.md`.

## Plan
- `backend/tests/integration/test_g02t12_security_center_ac_suite.py`, headed `# ac-test-author:
  ayushkbhatia`. Over HTTP against `create_app()`, the sign-in dependency answering as the
  persona: Felix (`security_admin`, the QI), Grace (`firm_admin`), Margaret (`quality_partner`,
  partner level), Daniel (partner level), Hannah (manager), a client principal, the agent
  principal; `security_center.v1`, `compliance.incidents` and `compliance.firm_export` on in
  `feature_flag_states`.
- **Against the stubs**, as T05: `STUBBED` lists the routes answering 501. A behaviour test on a
  stubbed route asserts the 501 and stops; the implementing task removes its routes from
  `STUBBED` and the full assertions run. With `STUBBED` emptied, every behaviour test fails
  against the stubs.
- **Run in full now** (no live route needed): the matrix (every write denies agent and system,
  fresh MFA on the decisions and policy writes, safeguards edits by `security_admin` only, Margaret
  read-only), the fresh-MFA register, the database (incidents stay insert-only for the app beyond
  the status), request validation (no field turns MFA, the passwordless code or the portal floor
  off; 422 before any handler), fresh-MFA refusals and wrong-role refusals (the matrix answers
  before the stub), client 404 and agent 403 on every route, no retention write route, and the
  support approval by `security_admin` on SPEC-012's live routes (DEC-72).
- No `xfail` is needed: nothing in the suite fails today except through the `STUBBED` mechanism.
- Known gap for G-02-T14: AC-15's positive path (enforcement after a verified admin SSO sign-in)
  needs the fact T14 stores for "verified"; the suite proves the 409 refusal and, once live, that
  turning Require SSO off and shortening limits succeeds. T14 adds the seeding of a verified
  sign-in to `test_ac15_*` when it lands.

## Files
- New: `backend/tests/integration/test_g02t12_security_center_ac_suite.py`.

## Rollback
Delete the file.

## Progress log
- 2026-10-26: written; one targeted run: all 55 suite functions (with their parameters) passed
  against the stubs together with the contract test and `tests/contracts/compliance_kernel`
  (891 passed in the run; the only failures were the two route-introspection tests awaiting
  regeneration and two contract-test bugs since fixed). Run in full now: matrix and fresh-MFA
  register, `security_incidents` UPDATE/DELETE refused for the app, 422s on locked-floor fields,
  wrong-role and stale-factor 403s, client 404 and agent/system 403 on all 21 routes (which also
  proves `schedule/approve` is not shadowed by Q-02's `/{export_id}/approve`), and SPEC-012's
  support approve and revoke by `security_admin`. No xfail. Not covered here: AC-17's idle
  refresh failure (a BFF test for G-02-T14) and AC-15's positive path (T14 seeds a verified
  admin SSO sign-in).
