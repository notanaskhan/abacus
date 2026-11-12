---
id: TASK-7418
title: "F-07-T04: TPL-04 scripted session fixtures: ScriptedRunSource scripts on the Brightwater Hale export (8 session rows, discovery table, two-step question, progress, result, xlsx artifact, CCH token failure)"
spec: SPEC-652
acceptance_criteria: [AC-2, AC-4]
risk_zone: green
status: in-review
branch: s38-f07-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: F-07-T04
---

## Objective
Fixture tests prove 79 + 145 = 224, 98 + 64 + 62 = 224, 10 + 26 + 26 + 17 = 79 and 120 of 241 =
50%, and lint L10 finds no kit sample person.

## Plan
- `apps/web/src/fixtures/seed/tpl04-sessions.ts`: discovery counted from `e0.tax-returns.json`
  (224 returns; open and done by the registry's words; per-office totals; the four stage groups),
  engagements 214 and binders 241 verbatim from the handoff; the eight session rows (seed personas;
  two "via Agent"); each artboard's thread as C6 `SessionItemOut` items (a discovery and the 1 of 2
  question; b empty with the suggested prompts and context chips; c running tool cards and
  "120 of 241 · 50%"; d the result and the xlsx artifact; e the CCH Axcess token failure); the
  running frame's `ScriptedRunSource` script.
- Test `tpl04-sessions.foot.test.ts` (13 pass).
- Rollback: revert.

## Partial
- `lib/chat.js` and `lib/agents.js` are the handoff canvas's scripts; their semantics are ported
  here as C6 items (no file is copied). The fixture-mode handler for `GET /v1/workbench/sessions/
  {id}` and the TPL-04 gallery page draw these with F-07-T03's thread (S39 specimen row).

## Progress log
- `2026-11-12` — Built (S38). 13 vitest pass; tsc and biome clean.
