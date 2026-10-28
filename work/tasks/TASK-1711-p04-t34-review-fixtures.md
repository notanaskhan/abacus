---
id: TASK-1711
title: P-04-T34 C3 TypeScript fixtures and handlers
spec: SPEC-360
acceptance_criteria: [AC-9]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T34
branch: s14-p04-t34
created: 2026-10-28
updated: 2026-10-28
---

## Objective
C3 in fixture mode for every SHL-09 to SHL-16 artboard (44: SHL-09 6, SHL-10 8, SHL-11 8, SHL-12
9, SHL-15 7, SHL-16 6), at E0 Mon Sep 14 9:24 AM CT and the Sep 24, Oct 1 and Oct 6 snapshots,
typed against the generated client. Acceptance (backlog row): "Every SHL-09 to SHL-16 artboard
renders from typed fixtures and no draft type is left in fixtures/contracts."

## Plan
- `apps/web/src/fixtures/seed/review.ts`: the frames P-04-T09 and T12 drafted inside
  `fixtures/contracts/review-grammar.test.ts` move here, exported, plus every request and write
  answer the tests built inline (SHL-12 a′, b, e, f; SHL-11 a, e, f; SHL-10 b, d, e, f; SHL-09 a,
  c, e; SHL-16 a–f; SHL-15 a–e) and the one frame no test drew (SHL-10 e, the batch before
  approval). `REVIEW_ARTBOARDS` lists the 44 with viewer, clock (the handoff READMEs' "Rendered"
  column), frames (route, schema, status, body, record params) and requests.
- `apps/web/src/fixtures/handlers/review.ts`: `reviewHandlers(artboard?)` serves the frames by
  route (narrowed to the record the path names; another id is 404); `reviewScenarios(screen)` is
  one Scenario per artboard on E0. The UI tasks (P-04-T41 to T52) re-export them per screen.
- `fixtures/contracts/review-grammar.test.ts` asserts on seed frames only; `dollars` formats in
  code (no `toLocaleString` outside tests).
- Prime states are `ap`, `app` and `ep`, as the handoff names the screenshots.
- Rollback: revert the branch.

## Acceptance
| Check | Test |
|---|---|
| 44 artboards in the handoff's order, each at E0 or a snapshot, each viewer a seed person | `apps/web/src/fixtures/review.foot.test.ts` |
| Every answer and request is its OpenAPI schema on a served route and status | same |
| Each scenario serves exactly what its artboard draws | same |
| No frame drafted in `fixtures/contracts` (the suite imports them all) | `fixtures/contracts/review-grammar.test.ts` |

## Progress log
- `2026-10-28` — Built. `vitest run src/fixtures` 40 files, 443 passed; tsc clean for fixtures;
  eslint clean on the four files. Found while checking: `screens/HOME-01/hosts.test.ts` (I-01-T13,
  #567) missed the required `work_item_id` on `HumanGateOut`; fixed on #567's branch.

## Handoff
- **Current state:** PR open, held for the S14 batch (stacked on #568).
- **Next:** P-04-T36 replaces these frames with the scenario's events through the services.
