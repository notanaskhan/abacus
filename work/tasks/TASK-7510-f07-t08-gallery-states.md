---
id: TASK-7510
title: F-07-T08 T4 template states and the TPL-04 specimen in the gallery
plan_key: F-07-T08
spec: SPEC-652  # AC-1 to AC-5
acceptance_criteria: [AC-1, AC-4, AC-5]  # 11 artboards under ?st= with a frozen ScriptedRunSource; the action log records each intent; no console errors
risk_zone: green
status: in-review
branch: f07-t08-gallery-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
T4a–T4f and TPL-04a–e in the gallery for Hannah Leclerc at E0; the Agents and Connect tabs mount
F-05's T5 specimens; intents for Bug (run-trace), Create Agent… (edit-agent:new) and Save to Files.

## Plan
- `apps/web/src/gallery/specimens/T4/` (new): `index.tsx` (`T4Artboard`, `Tpl04Artboard`, the
  sessions frame on the F-07-T04 seed, WB-06's agent frame, the running frame's
  `ScriptedRunSource` frozen on its running page under `?static=1`, the action log), `copy.ts` (T4a
  prompts and T4f's WB-06 words verbatim), `T4.test.tsx`.
- Registered in `gallery/specimens/index.ts` as `T4` and `TPL-04`; `@abacus/ui/specimens` exports
  `T5Board` for the Agents and Connect tabs (tpl-05a, t5e).
- T4's states map onto the seed session (a empty → TPL-04b, b running → c, c awaiting → a, d → d,
  e → e); T4's parity is Tier D, so the geometry is what is measured (DEC-4510).

## Progress log
- `2026-11-12` — Built (DEC-4510). Tests run at the S39 end pass.
