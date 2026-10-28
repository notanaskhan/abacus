---
id: TASK-1714
title: P-07-T60 ENG-13 roll-forward wizard re-skin on O6
spec: SPEC-321
acceptance_criteria: [AC-30]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T60
branch: s14-p07-t60
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ENG-13 on O6 over the roll-forward v2 draft (P-07-T55): five steps (Source · What to carry ·
Template version · Team · Review), Carry · Skip per v1 category with autosave, the live Carrying
card, the gate block, team rows with independence chips, Discard, and Create. d and e are the live
shapes; a, b (attest carry) and c (template conflicts) are fixture-only. Acceptance (backlog row):
"Scenarios a to e pass with axe and production shows only the v1 carry categories."

## Plan
- `src/screens/ENG-13/{index.tsx, copy.ts, scenarios.ts}`; fixtures `src/fixtures/scenarios/ENG-13.ts`
  (handlers for GET/PATCH/DELETE/create on the generated client's shapes, one fresh draft store per
  scenario; Granite Peak and Northwind facts from the seed, Tessellate from the handoff).
- Fixture-only rows are a `preview` prop (like ENG-03's consents), drawn only when
  `PLANNED_VISIBLE`; the route passes none. "Create & draft letter" (N-02) is fixture-only too.
- Gallery registration; vitest per artboard + a production-build test; axe through
  `e2e/screens/ENG-13.spec.ts` on the gallery.
- Manifest stays planned (ENG-02's reason), with a note; screen contract updated (DEC-805 actions).
- Rollback: revert the branch.

## Acceptance
| Check | Test |
|---|---|
| a–e render; carry toggles autosave on `seen_version`; c holds Next until both conflicts are chosen; d's 24 requests as Draft; e's Create with an Idempotency-Key and the toast | `apps/web/src/screens/ENG-13/ENG-13.test.tsx` (10) |
| Production draws only the four v1 rows, no preview, no conflicts, no letter button | `ENG-13.production.test.tsx` (4) |
| Axe: nothing serious or critical on a–e | `e2e/screens/ENG-13.spec.ts` (5 passed) |

## Progress log
- `2026-10-28` — Built. ENG-13 vitest 14 passed; `vitest run src/routes src/screens/gallery
  src/fixtures src/app-core` 596 passed; Playwright axe 5 passed; tsc and eslint clean. Two kit
  facts learned: the Wizard's `actions` replaces the whole footer group (so e builds Save draft,
  Create and the planned letter button itself), and a Segmented always holds a selection (so c's
  choices are a pressed-button pair).

## Handoff
- **Current state:** PR open, held for the S14 batch (stacked on #571).
- **Next:** wire ENG-02's "Roll forward…" with ENG-02's live route (routes/firm); parity (P-07-T63).
