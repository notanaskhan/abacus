---
id: TASK-7511
title: F-07-T09 T4 lock before W-02 (parity, axe, keyboard)
plan_key: F-07-T09
spec: SPEC-652  # AC-1 to AC-5
acceptance_criteria: [AC-1, AC-4, AC-5]  # TPL-04a–e Tier B; T4 Tier D; axe 0 serious or critical; keyboard suites
risk_zone: green
status: in-review
branch: f07-t09-t4-lock
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Lock T4 before W-02 starts: Tier D for T4, Tier B locked for TPL-04 (spinners, live dot and reveal
masked), axe on every state, a keyboard suite for the QuestionCard, the Composer and the JumpFab.

## Plan
- `docs/design/parity-manifest.json`: `tpl-04a…e.window` (Tier B, `locked`, masks `[data-spinner]`,
  `[data-pulse]`, `[data-reveal]`), `t4a…f.window` (Tier D with the DEC-4510 deviation: the seed
  session, not the kit's sample threads); sources pinned by sha256 from the handoff PNGs.
- `apps/web/e2e/visual/tier-d-workbench.spec.ts`: tabsbar 60, panes y106–848 (742), list 358 or
  320 (WB-06) at x12, chat 1008 at x380, headers 46, composer 50, ask header 36 and 9 above the
  composer, on all 11 boards.
- `apps/web/e2e/specimens/f07-t4.spec.ts`: axe on every T4 and TPL-04 state; QuestionCard 1–9 /
  Enter / Esc; Composer Enter and Shift+Enter; JumpFab focus.
- `packages/ui/src/agent/chat/t4-keyboard.test.tsx`: the same paths at unit level.
- The gallery artboards carry `data-artboard` for the manifest's selectors.

## Partial
- The Tier B pixel run and axe need the visual project (`ABACUS_VISUAL=1`, Playwright) at the end
  pass; the plan's "merged in the Thu Apr 27 2028 batch" is the S39 batch here.

## Progress log
- `2026-11-12` — Locks, specs and suites written (DEC-4511). They run at the S39 end pass.
