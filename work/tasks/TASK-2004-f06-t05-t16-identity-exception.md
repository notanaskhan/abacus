---
id: TASK-2004
title: F-06-T05 T16 identity and exception states
spec: SPEC-400
acceptance_criteria: [Story 1.1, Story 1.4, Story 1.5, Story 1.7]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T05
branch: s15n-f06-t05
created: 2026-10-29
updated: 2026-10-29
---

## Objective
T16's provider-mode identity and exception states (DF-11, DF-12): `ProviderSigningFrame` (titled,
sandboxed, https only; redirect presentation as one call to action), the pending-confirmation
state after the provider returns (never Completed until the server says so), DF-11's
`VerificationFailedCard` (no retry, no countdown, no other method; the paper-form path naming the
preparer), and the `DeclineDialog` (four reasons and a note; Decline waits for a reason; one call).

Acceptance (backlog row): "Provider mode shows Completed only after the envelope status says so,
TPL-16e offers no retry and names the paper-form path, Decline stays disabled until a reason is
chosen, and no native identity component or NativeIdentityAdapter is exported."

## Plan (amber)
- `packages/ui/src/signing/outcomes.tsx` (new): the four parts plus the phone parts (T06).
- `signing/types.ts`: `SigningOutcomeCopy`; `SigningCeremonyProps` gains `copy`,
  `providerReturned`, `onDecline`, `declineForceState` (and T06's `layout`, `stickyBarHeight`).
- `templates/signing-ceremony/SigningCeremony.tsx`: the well hosts the provider during verify, the
  DF-11 card on failure; the steps pane shows pending confirmation; the kit owns the decline dialog
  when given copy and `onDecline`.
- `apps/web` TPL-16 specimen: states e, f, pending; copy additions (DEC-1053).
- No native identity component: no `KbaCard`, `EmailCodeCard`, `AdoptSignatureDialog`,
  `NativeIdentityAdapter` or `mode="native"` (Story 1.7); a and c stay Tier C screenshots.

## Progress log
- 2026-10-29: built with F-06-T06 in one PR (the template carries both). Tests written in
  `TPL16.test.tsx` (e, f, pending, provider frame); not run yet (end review). tsc and eslint clean.
