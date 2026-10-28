---
id: TASK-1703
title: F-06-T04 T16 SigningCeremony frame and TPL-16b/d
spec: SPEC-400
acceptance_criteria: [AC-1, AC-2, AC-3, AC-8]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T04
branch: s14-f06-t04
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The T16 signing kit in provider mode: `SigningCeremony` (template) and its L2 parts (EnvelopeHeader,
SigningDocumentList with SignerChips, SignFieldLayer, SigningSteps, AuthorizingCard, CompletionCard and
EvidenceList), with specimens T16b/c and TPL-16b/d.

## Plan
- Types first: `packages/ui/src/signing/types.ts` (EnvelopeVM per F-06.md §5.2; statuses typed against
  the C2 registry rows F-06-T03 added). C7 v1 has not merged: no stub file; N-02 maps C7 onto
  EnvelopeVM when it lands.
- Parts in `packages/ui/src/signing/{parts,sign-field-layer}.tsx`; template
  `packages/ui/src/templates/signing-ceremony/SigningCeremony.tsx` on `AppShell variant="portal"`.
- Specimens: T16 in `packages/ui/src/specimens/signing.tsx` (gallery kit `t16-signing-ceremony`);
  TPL-16 in `apps/web/src/gallery/specimens/TPL-16/` from the E6 seed, registered at
  `/components/screens/TPL-16`. Gallery eslint override lets specimens read `fixtures/seed/*`.
- No registry, flag, matrix or dependency edit. Rollback: revert the branch.

## Per AC
| AC | Tests |
|---|---|
| AC-1 | `SigningCeremony.test.tsx`: "1 of 2 signed" from server counts (and 7 of 9 stays 7 of 9); `TPL16.test.tsx`: chips, $2,296 and $410 |
| AC-2 | only the viewer's field is a control; Dev's field is text; Sign here tab focuses the viewer's next open field; field and CTA call `onSignField` with it; non-signer → restricted, no page |
| AC-3 | T16c completion card (5 rows, the board's); TPL-16d six evidence items attributed to Mira; no TIN pattern |
| AC-8 | steps an ordered list with `aria-current="step"`; CTA is a HumanAction (`data-human-verb="Adopt"`); no "Agent" or "Accrued" text |

## Decisions made during this task
See `packages/ui/src/tokens/DECISIONS.md` "T16 SigningCeremony frame and TPL-16 b, d (F-06-T04)".

## Progress log
- `2026-10-28` — Kit, specimens and tests built. Targeted: packages/ui vitest (jsdom) signing-ceremony + attribution 24 passed; apps/web TPL-16 4 passed; eslint and tsc clean on touched files. Parity, axe and the Playwright walk wait for the batch (no Chromium run in this session).

## Handoff
- **Current state:** built, PR open (stacked on F-06-T03), held for the S14 batch.
- **Exact next step:** F-06-T05 (provider frame, verification failed, decline dialog) and T07's independent suite in S15.
- **Known gaps:** Tier B/D parity and axe not run; `f06-signing.spec.ts` walk not written (F-06-T13 lock).
