---
id: TASK-7508
title: F-07-T06 QuestionCard (chat-ask DecisionCard variant)
plan_key: F-07-T06
spec: SPEC-652  # AC-5
acceptance_criteria: [AC-5]  # T4c and TPL-04a Tier D; Next emits exactly one answer with the chosen key; Previous disabled on step 1; no gate verb
risk_zone: amber
status: in-review
branch: f07-t06-question-card
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The `question` wire kind's card above the composer: n of m stepper, olive radio with check,
preselected default, Skip/Previous/Next, "Something else…", keys 1–9/Enter/Esc, composer live.

## Plan
- `packages/ui/src/agent/chat/question-card.tsx` (new file only; nothing live changes): props are
  SPEC-652 AC-5's payload (`question_id`, `steps[{q, options[{key, title, detail}], other,
  preselect}]`, `skipText`, `skipDefault`, `n`, `m`); `onAnswer` once per Next with
  `{question_id, step, key}`, `{skipped: true}` only on Skip; `onSomethingElse` and `onEscape`
  hand focus to the consumer's composer. Geometry from the handoff: header 36, "?" chip 19 on
  nested, radio 17 (selected `bg-green` with a white check), options 13.5 / detail 12.5/1.35
  ink-2, footer buttons 30 (md), card radius 12 `shadow-ask`. Agent strings through AgentText.
- Exported from `agent/chat/index.ts`; ChatThread's `above` slot already places it.
- Tests `question-card.test.tsx` (TPL-04a's ask verbatim).

## Partial
- Tier D for T4c and TPL-04a runs in F-07-T09's parity lock (the gallery states land with F-07-T08).

## Progress log
- `2026-11-12` — Built (DEC-4508). Tests run at the S39 end pass.
