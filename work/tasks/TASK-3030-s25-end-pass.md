---
id: TASK-3030
title: S25 end pass (regenerate, gates, tests, security review)
spec: SPEC-000  # S25 end review over #1075–#1104
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s25-end-pass (the S25 stack tip s25-p04-t57 + origin/s24-end-pass-fix)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
One pass over the S25 build (#1075–#1104): regenerate every generated file, stage-1 gates,
targeted unit, integration and web tests, a security review of the red diffs, one round of fixes
and at most one re-review; then CI once, on the batch.

## Progress log
- 2026-11-02: merged origin/s24-end-pass-fix (#1095, the #1074 CI repair) into the stack tip;
  `make regenerate` changed only the generated security tests; one alembic head (0653).
- Security review (red: N-04-T01/T03, A-04-T43, A-06-T09/T10, A-05-T18, A-05-T21):
  - S1 (fixed): `evidence.reveal_field` wrote the reveal row and audit event but not the Q-02
    `access_events` row `reveal_pii` writes before a value leaves. Now recorded, subject
    `ebp_participant` and the record id, with the `pii_tin`/`pii_dob` flag; the participant
    reveal passes the evidence PII kind (`dob`, not `date_of_birth`).
  - S3 (fixed): `assert_masked`'s date-of-birth check got no dates on the mode's real path; the
    comparison now returns the dates of birth code opened and the mapping passes them.
  - S2 (accepted): the `ebp_attribute` mapping opens a census DOB in code, on the agent run's
    path, only for a hire-date difference; the value never enters a model input or a fact (only
    the engine's note does). Recorded, not changed.
  - Adjustments routes gate on the entry's work item before every read and write; no finding.
- Gates: ruff E501 in the generated `_statuses.py` (N-04-T01's derived-status comment): the
  status-vocabulary generator now wraps it. Prettier (the enforced FE formatter, not biome)
  reformatted ten S25 FE files.

- 2026-11-02 (tests): unit 37,509 pass (the two classification tests need weasyprint's system
  libraries, absent locally: S25's contracts checked by hand, no unclassified field; the
  five-second generation test passes alone, slow only under load); web 3,004 of 3,004; the
  targeted integration, contract and security files pass after the fixes above plus: 0654 (0642's
  hash CHECKs), audit refs, the minutes call, the planning actions, the `pii_reveals` grant, S5,
  and the schema-check, worker, catalogue and stub expectations.
- Not run locally: the full integration suite and e2e (CI's batch run covers them).

- 2026-11-02 (CI on #1106, run 41502162260, red): 96 failures. Most came from one cause: G4's
  provider (A-04-T43) ended Fieldwork's record mode, which the seed loader and the A-01 record-mode
  tests still used. Also: the drafter's agent context reached two person-only reads (requests'
  `user_id`, the flag raiser's `created_by`); three status fields; A-05-T19's tests on the dev
  S3; workpaper export determinism. Fixed under DEC-2078. Main's own reds (portal recovery,
  a05t07 and a03t10 determinism) are #1105's, merged in. Left as main flakes: a random hex run
  read as a TIN (error tracking span id) or a sign-in code (mention email).
- Mistake made twice: a `cast` to `AuthContext` around an agent context hid a crash both times.
  Typed the slots for the agent instead; a lint rule against `cast(AuthContext, ...)` is worth
  adding.

## Decisions made during this task
DEC-2077 (end-pass fixes), DEC-2078 (batch CI fixes).
