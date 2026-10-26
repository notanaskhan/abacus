---
id: TASK-1321
title: SHL-08 masked PII (c), password-locked (d) and in-document search (P-03-T20)
spec: SPEC-322
acceptance_criteria: [AC-26, AC-27, AC-28, AC-31, AC-33, AC-34, AC-21]
risk_zone: amber
status: in-review
epic: P-03
plan_key: P-03-T20
branch: s10b-pii-unlock-viewer
created: 2026-10-26
updated: 2026-10-26
---

## Objective
SHL-08 states c and d and the search capsule on the EvidenceViewer (P-03-T14), from the handoff
frames C and D (spec.md; revision.md adds nothing for c or d), through the generated client only.

## Plan
- `screens/SHL-08/MaskedValue.tsx`: `useMaskedReveal` calls the SDK's `revealPii` directly (no
  React Query, so neither cache holds the answer); the value lives in hook state, cleared on Hide,
  after `expires_in`, on a version change and on unmount; the logged line under the toolbar and a
  polite live region; 403 `mfa_required` opens the step-up dialog (`domain/audits` RevealStepUp,
  the shell's ConfirmItsYou words).
- `screens/SHL-08/UnlockPanel.tsx`: Lock tile, title, body, `type=password autocomplete=off`
  field cleared on submit, Unlock, "That password didn't open the file." tied by
  `aria-describedby`, 429 wait, "Ask ‹client›…" through the host's `onAskClient`; flag off or no
  `evidence.unlock`: "Ask …" only. Success re-asks the manifest (the derivation's pages).
- `EvidenceViewer.tsx`: wires both, plus server search (`viewerSearch`) whose hits light as
  regions with a count line. Kit (`packages/ui` SourceViewer): `RevealSlot.onHide/hideLabel`
  (the Hide chip) and `onFind` (server search); both optional, old behaviour unchanged.
- Fixtures: reveal and unlock handlers in `fixtures/handlers/trust.ts`, the W-2 value and the
  Halvard derivation in `fixtures/seed/trust.ts`, `variant()` scenarios (stale MFA, flag off,
  limit) in `fixtures/scenarios/SHL-08.ts`.
- Tests: `SHL-08.reveal-unlock.test.tsx`, one per state and refusal.

## Rollback
Revert the commit; the kit props are optional.

## Progress log
- 2026-10-26: built. Partial: "Ask Jonah & Claire Feld…" calls the host's `onAskClient` with
  `{versionId, fileName}`, but no host passes one yet (the SHL-14 composer has no prefill entry
  and needs a binder id the viewer doesn't know), so in the artboard it is the handoff's
  tooltip-only link (disabled with its destination as the hint), as "Open in Files" is. DEC-426.
- 2026-10-26: vitest `src/screens/SHL-08` 39 passed (10 new), `packages/ui` viewer 28 passed;
  tsc, eslint and prettier clean on touched files. Playwright skipped (chromium mismatch).
- 2026-10-26: security review L4: stale reveal answers dropped (generation refs);
  `MaskedValue.test.tsx` (control and the dropped case; fails without the fix).
