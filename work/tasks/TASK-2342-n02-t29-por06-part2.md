---
id: TASK-2342
title: N-02-T29 POR-06 part 2 (8879-PE, joint filers, dated letters, DF-11)
spec: SPEC-381
acceptance_criteria: [AC-11]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T29
branch: s18-n02-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
POR-06 d, e, f and h on the T16 kit, over C7's portal routes (live since N-02-T23):

- **d** Form 8879-PE: identity verification runs inside the provider's view (DF-12); the steps pane
  says "Identity questions" and carries the authorizing card (the handoff's IRS note).
- **e** joint filers (Feld Form 8879): "1 of 2 signed", per-signer chips, the signing order, and
  "Each spouse verifies and signs separately. Jonah gets his own link."
- **f** a representation letter dated as of the report date: "Continue to sign" stays disabled
  until the server says signing opens; the amber note names the date. Fixture-only until A-07
  registers `rep_letter`.
- **h** DF-11: identity check failed, the paper-form card, no retry.

Acceptance (backlog): "Scenario tests for d, e, f and h pass, h offers no retry, and Owen's letter
signs end to end on staging."

## Plan
C7's portal view names no other signer, no identity method, no envelope family and no date gate
(N-02-T26 recorded the gap). Contract first, additive (DEC-1388):

1. `PortalEnvelopeView` gains `family` (the envelope's policy family), `identity_method` (the
   viewer's), `signers` (`PortalSignerOut`: id, name, role, routing group, status, signed_at, `me`;
   in order) and `signing_opens_on` (the `date_as_of` while the firm's today is before it, else
   null: the same check `before_date_as_of` makes). `portal.py` fills them; `make generate`.
2. Frontend: `domain/signing/portal.ts` unchanged; `screens/POR-06` maps signers, method and the
   date gate onto the kit (`others`, chips, steps, `authorizing`); copy for d, e, f.
3. Fixtures: seed d (Owen's 8879-PE, KBA), e (Feld 8879, Claire signed, Jonah pending), f (Dana's
   Northwind rep letter, Oct 9), h (Owen's 8879-PE, verification failed); scenarios `d`, `e`, `f`,
   `h`; handler answers 409 `before_date_as_of` for f.
4. Tests: `POR-06.test.tsx` d, e, f, h (h: no retry, no Continue); a backend unit test on the
   view mapper and an integration assertion on the new fields.
5. Docs: `docs/screens/POR-06.md`, `docs/contracts/c7-envelopes.md`, DEC-1388.

No migration, no flag. Rollback: revert the PR (additive fields only).

Out: the staging walk with the demo account (a human step: Owen's letter on staging), Tier C lock
and Playwright (N-02-T43, N-02-T40).

## Progress log
- `2026-10-31` — plan written; building.
- `2026-10-31` — built. C7 portal view additions, `make generate`; POR-06 d, e, f, h with tests
  (36 pass at 1400 and 390), fixture suites (109), C7 consumer contract (47), portal integration
  suites N-02-T23 and N-02-T31 (39). The h test caught the container still offering "Continue to
  sign" under the DF-11 card: DF-11 is now its own phase with no action. Gates clean on the
  changed files; banned-pattern hits in `signatures/portal.py`, `test_c7_stubs` and the
  error-codes drift exist on main unchanged (other sessions').

## Handoff
- **Current state:** PR open.
- **Exact next step:** merge with CI; then the human staging step: Owen's letter end to end with
  the demo account.
