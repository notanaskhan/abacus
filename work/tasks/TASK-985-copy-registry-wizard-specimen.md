---
id: TASK-985
title: Copy registry (L2) and the O6 wizard specimen TPL-18a to e with the type catalogue and gate cards (F-05-T32, F-05-T38)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T32; F-05-T38
branch: f05-t32-t38-copy-wizard
created: 2026-10-23
updated: 2026-10-23
---

## Objective
F-05-T32: "L2 fails on emoji, exclamation marks in agent keys, three dots on dialog openers and
Accrued in portal namespaces." F-05-T38: "TPL-18e disables Create behind the Gate G1 card, and the
type catalogue comes from data with Single audit fixed at Coming soon."

## Scope
**In**
- `apps/web/src/copy/registry.ts`: `defineCopy(id, copy, rules?)` returns the copy unchanged and
  records its namespace; `lintCopy` is L2 (emoji, "!" in agent keys, "..." anywhere, dialog openers
  without "…", the product's name in portal namespaces, "task" outside allow-listed close keys,
  "Todo" unhyphenated). Surface comes from the id (`POR-*`, `*.portal`).
- `apps/web/src/copy/common.ts`: `common.firm` and `common.portal` from the C-20 and C-22 kits'
  words (`STATE_COPY`); the portal variant has its own error body and no agent words.
- `apps/web/src/copy/copy-registry.test.ts`: L2 over every `screens/*/copy.ts` and every registered
  namespace, plus one deny case per rule.
- `packages/ui/src/templates/wizard-kit.tsx`: `TypeCatalogue`, `TypeCard`, `typeAvailability`,
  `GateCard` (met, needs, blocked), `WizardSummary`; exported from `@abacus/ui` for ENG-03 (P-07).
- `Wizard` (O6): `subtitleAt="start"` for TPL-18's "Draft saved 9:05 AM", and the 220 step list
  with padding 10 and pill rows, as TPL-18 draws it.
- `packages/ui/src/specimens/wizard.tsx`: TPL-18a to e over Engagements, live (pick a type, Next,
  Back, reopen a done step, Request consent with the letter); parity entries `tpl-18.a` to `e`.

**Out**
- Migrating the existing screens' `COPY` objects onto `defineCopy`: L2 already reads them (their
  surface from the screen id), and each screen moves when it is next revised.
- The ENG-01 index under the scrim (P-07); Escape, Create and the toasts' destinations (ENG-03).

## Definition of done
- [x] `wizard-kit.test.tsx` (13 cases) and `copy-registry.test.ts` (10 cases) green
- [x] axe over every specimen and with forced colours clean; INV-1 and INV-5 sweeps green
- [x] tsc, eslint, prettier for `packages/ui` and `apps/web`; `make check-fast` with the bundle budget

## Progress log
- 2026-10-23: built. The L2 "To-do" rule bans only the closed forms ("Todo", "todos"): "To do" is
  the portal's status group (BND-02 preview, verbatim) and a verb phrase, so it stays (DEC-190).
  O6's specimen stages grew from 360 to 400 high: with the step list's new padding, a 360 stage
  made the list scroll with nothing focusable in it (axe `scrollable-region-focusable`).
  Parity, measured locally against crops of the handoff PNGs: every template window renders
  2800 x 1722 against a 2800 x 1720 baseline (T2, T7, T15, TPL-07, TPL-15 and TPL-18 alike), so the
  size check reports before any pixel count; F-05-T49 takes this up before it locks.
  `a11y.spec.ts` "every overlay a specimen opens" timed out at 240 s on this machine under a load
  average of 10 to 18, with and without the TPL-18 specimen registered.
