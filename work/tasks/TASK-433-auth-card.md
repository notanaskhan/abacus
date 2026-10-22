---
id: TASK-433
title: T15 AuthCard (400 card and 720 single page) with six code boxes; T15a to T15c and TPL-15a to TPL-15j (F-05-T37)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T37
branch: f05-t37-auth-card
created: 2026-10-23
updated: 2026-10-23
---

## Objective

"TPL-15b waits for all six digits, TPL-15d says invites last 14 days, and TPL-15e and TPL-15j
render at 390px without horizontal scroll." (F-05-T37)

## Scope

**In** (`packages/ui/src/templates/auth-card.tsx`, exported from the package root)

- `AuthFrame` (no toolbar; `card`, `page` and the 390 `mobile` layout with the 56 header; the
  Secured by footer only when the brand turns it on), `AuthBrand`, `AuthCard` (400, radius 14, e2,
  padding 28 28 24, title 16/500, optional red or green tile), `AuthFooter` (Privacy · Terms · Help
  from the branding links), `AuthButton` (36 full width), `AUTH_FIELD` (the boxed 36 field),
  `CodeInput` (six 44 × 52 boxes: auto-advance, Backspace, arrows, paste and autofill),
  `AuthChoices` (radio rows), `AuthPage` (the 720 paper with a letterhead; Gelasio legal heading).
- Specimens `t15-auth-card` (T15a to T15c) and `tpl-15` (TPL-15a to TPL-15j): Jonah Feld's
  invite, code, second step and expired invite; Summit Trail and Alpine Ridge's confirmations,
  submitted and answered; the two 390 frames. The second steps come from the brand's sign-in
  methods; the difference ($4,300.00) is computed in cents.
- Tier D rows: the card's width, radius and padding, the code box, the 720 paper, and TPL-15e and
  TPL-15j at 390 with no horizontal scroll. Tier B (report-only) parity entries for the 13
  artboards, pinned.

**Out**

- The BFF auth client and the real flows (POR-01, P-08-T09/T19); email verification on POR-17
  (R-01). The specimen's Verify email stays a button.
- The firm's SHL-06 card (hosted pages first, DEC-22).

## Plan

Green zone. No migration, registry, flag or dependency. Rollback is a revert.

Tests (`templates/auth-card.test.tsx`, 16):

- TPL-15b waits for six digits → "TPL-15b waits for all six digits; six typed or pasted enable
  Continue".
- TPL-15d → "TPL-15d says invites last 14 days, with Send a new invite link".
- 390 without horizontal scroll → "TPL-15e and TPL-15j render at 390, fluid, with no fixed width
  over 390" (jsdom), and Tier D "tpl-15e / tpl-15j renders at 390 with no horizontal scroll" in a
  real browser.
- The code boxes (advance, Backspace, paste, autofill, size), the brand's second steps and no
  password field, the confirmation (balance from the decimal, Submit gate, the computed difference,
  the receipt, the answered link), T15a to T15c, the card geometry, the white label.

## Definition of done

- [x] `vitest run src/templates/auth-card.test.tsx`: 16 passed.
- [x] ui tsc, eslint, prettier.
- [x] Tier D (`playwright --project=visual tier-d.spec.ts -g T15`): 3 passed.
- [x] Parity run: 13 entries, report-only.
- [x] `e2e/a11y.spec.ts` over the gallery.

## Progress log

- `2026-10-23` Built and checked as above. Parity captures are 2 device px taller than the crops
  because the artboards sit at a fractional y on the long gallery page (same as TASK-430); the
  single-artboard specimen route (F-05 I1) resolves it before F-05-T49 locks the frames.
- `2026-10-23` INV-1 (`e2e/inv.spec.ts`): Send is a human verb, so "Send me a code", "Send a new
  invite link", "Send Response" and the C-16 reply's Send render through `HumanAction` for the
  named client. The Request kit (TASK-430) gains a `viewer` prop for it: without a named person the
  reply composer is not offered. Caught before CI by running the gallery's e2e set locally.
- `2026-10-23` SPEC-048 AC-8 (`components.spec.ts` reduced motion): the held More sheet (T7-M) and
  the held Ignore menu (TPL-07f) kept a filled `ac-reveal` animation. The reveal now runs only for
  a menu the person opens with motion allowed (`useMotion`). Gallery e2e set (`components`,
  `a11y`, `e3`, `inv`): green.

## Decisions made during this task

Recorded in `packages/ui/src/tokens/DECISIONS.md`, "T15 AuthCard (F-05-T37)".
