---
id: TASK-1131
title: POR-01 frontend part 2 - c two-step (authenticator code, trust toggle, backup code), c′ setup (key, first code, 8 backup codes once), d invitation acceptance (P-08-T19)
spec: SPEC-320
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13]
risk_zone: green
status: done
epic: P-08
plan_key: P-08-T19
branch: s7-p08-invitations
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Scenario tests for c, d and the setup state pass in fixture mode, and backup codes cannot be shown twice." (P-08-T19; docs/screens/POR-01.md; DF-17.)

## Plan (green zone)
- `screens/POR-01/index.tsx`: steps `second` (c), `setup` and `codes` (c′), `invite` and `invalid` (d), `done`; copy in `copy.ts` (handoff words for c and d; P-08-T19's own for c′ and the failures, flagged).
- `domain/portal/sign-in.ts`: `signIn.mfa`, `mfaSetup`, `mfaSetupVerify`, `invitation.preview`, `invitation.accept` over the generated client (accept carries the invitee's bearer).
- `routes/portal/index.tsx`: `/accept` takes `#token=` into memory.
- Fixtures: `/mfa`, `/mfa/setup`, `/mfa/setup/verify`, `/invitations/accept` handlers; backup codes; d's token.
- Tests in `POR-01.test.tsx` (c, c′, d, the AVOID list over every state).

## Progress log
- 2026-10-24: built. 31 POR-01 tests pass (10 new); fixtures, routes, app-core and domain suites pass (470). c′ shows the `otpauth://` link and the manual key, not a drawn QR: no encoder is allowlisted (screen contract, Open gaps; human to-do). The fixture handlers outlive a sign-in, so second-step tokens and their guesses are keyed per challenge.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-276 | c′ without a QR encoder; the invitation token in memory; the order code → session → accept | No |
