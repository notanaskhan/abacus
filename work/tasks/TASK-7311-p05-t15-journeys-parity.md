---
id: TASK-7311
title: "P-05-T15: Journey E2E and parity: j23 step 6, j16 A1-A2, j03 step 15, j18 step 5, j27 step 4 with INV-1..5 and axe; lock SHL-17 and SHL-18 at Tier C"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-23]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: green
status: in-review
branch: s37-p05-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-05-T15
---

## Objective
The five named Playwright tests pass on staging with real auth and INV-1..5, axe finds no serious
or critical issue, and parity.json reports every artboard with SHL-17 and SHL-18 locked.

## Plan
- Gallery (`apps/web/src/screens/gallery.tsx`): SHL-17, SHL-18 and AUD-29 registered, one
  artboard per state on its own fixture scenario (and TAX-08, T-04-T34's drawer).
- Journeys (the harness runs axe and INV-1 to INV-5 after each step):
  `J23-audit-partner-morning.spec.ts` "j23 6: …", `J16-daily-practice.spec.ts` "j16 A1–A2: …",
  `J03-ebp-audit.spec.ts` "j03 15: …", `j18-audit-quality.spec.ts` "j18 5: the EQR reads via
  Agent activity before concurring", new `j27-insights.spec.ts` "j27 4: …"; shared
  `p05-support.ts`.
- Parity: `## Parity` tables in `docs/screens/SHL-17.md` (a–f C locked), `SHL-18.md` (a, b, b2, c
  C locked; d, e, f report-only), `AUD-29.md` (a–f C report-only), each host Tier D; the three IDs
  in `BUILT_PLANNED` so the parity run measures them before their hosts mount them.

## Partial
- The staging walk with real auth waits for P-05-T16's canary flip (Tue Mar 28, 2028); the five
  tests are `test.fixme` outside the fixture project until then.
- J27 step 4's own to-do ("Update skill BH-SK-410" for Hannah, due Oct 16) is not in the SHL-17
  seed; the fixture walk proves the create gate (b) and My to-dos (f). The seed slice for it is
  I-03's (INS-03).

## Progress log
- `2026-11-12` — Built (S37). Prettier clean; journeys and parity run at the end pass.
