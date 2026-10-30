---
id: TASK-1725
title: R-01-T31 Portal parity and accessibility (Tier C, Tier D at 390, axe, keyboard, L7 email crawl)
spec: SPEC-323
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T31
branch: s14-r01-t31
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Backlog row R-01-T31: "Tier C reports for all 44 artboards; POR-03, POR-04 and POR-14 P0 states
locked before M8; Tier D for the 390 layouts without PNGs; axe on every state, forced colours,
reduced motion, keyboard-only drop and sheet paths; L7 white-label crawl extended to rendered email
HTML and text at 600 and 390." Acceptance: "The P0 states are parity-locked at Tier C, no rendered
email or portal page contains Accrued, and axe reports zero serious or critical findings."

## Plan
- Parity: 35 window entries in `docs/design/parity-manifest.json` (POR-03 a–i, c2; POR-04 a–g;
  POR-14 a–f; POR-20 a–l), pinned to the handoff PNGs; `BUILT_PLANNED` so the screen parity run
  measures the POR screens the registry keeps planned (DEC-347); an entry's selector names the
  window inside the artboard. Measure, record Diff % in the contracts, lock what is within C.
- Gallery: POR-20 a–l artboards (a 1400 × 860 window); `&w=390` for POR-04 and POR-14.
- Specs: `e2e/screens/POR-20.spec.ts` (axe a–l; every template's rendered HTML and plain text at
  600 and 390 without "Accrued"), `e2e/screens/portal-a11y.spec.ts` (forced colours and reduced
  motion on every POR-03/04/14 state), `e2e/journeys/portal-keyboard.spec.ts` (drop and sheet
  paths by keyboard), `e2e/visual/tier-d-portal.spec.ts` (390 geometry).
- Fixes found on the way: focus returns to the request's title when POR-04 closes (it fell to the
  body); POR-04's screen spec read the sheet inside the artboard (it is a modal in its own layer).
- DEC-814.

## Acceptance
| Check | Result |
|---|---|
| Tier C reports | 35 artboards measured (POR-03 0.50–1.95 %, POR-14 0.72–1.72 %, POR-04 4.31–7.18 %, POR-20 2.49–4.26 %, j 69 %, d phone board) |
| P0 states locked at Tier C | POR-03 a–i, c2 and POR-14 a–e locked; **POR-04 a–d, g not locked** (over C's 3 %, open gap) |
| ADM-10's seven artboards | not measured: no frontend yet (R-01-T28) |
| Tier D at 390 | `tier-d-portal.spec.ts` 15 pass; targets ≥ 44 and POR-04 sheet from y44 are expected failures (open gaps) |
| Axe | POR-20 a–l, POR-03/04/14 every state under forced colours: zero serious or critical |
| No "Accrued" | every email template's HTML and text at 600 and 390; the portal crawl unchanged and passing |
| Keyboard | drop and sheet paths pass, focus returns to the request |

## Progress log
- `2026-10-28` — Built. Playwright: parity-screens POR 35 passed (4 host rows unmeasured, Tier D);
  visual parity.spec por-* 35 passed (report-only); tier-d-portal 15; POR-20 18; POR-04 14 (fixed);
  portal-a11y + POR-03 + POR-14 + ds-white-label 70; portal-keyboard 2 (fixture project). Vitest:
  routes, gallery, portal suites pass.

## Handoff
- **Current state:** PR open, held for the batch (stacked on P-07-T62).
- **Next:** POR-04's sheet rhythm (then lock its P0 states); 390 target sizes on the portal's mobile
  controls; ADM-10's frontend (R-01-T28) and its parity rows.
- 2026-10-30: POR-04 locked (DEC-839). The artboard drew the sheet as a live layer pinned to the
  viewport, 40 px above the window's y52, and its focus move scrolled POR-03 behind it. In frame
  mode the sheet is now held in the window over the scrim; with the Upload band, the 33 "Why we
  need it" band, the comment indent, the Upload glyph and the hidden description, a–d and g
  measure 1.92–2.55 % with no masks. Tier D 390: y44 holds; targets ≥ 44 × 44 stay open.
