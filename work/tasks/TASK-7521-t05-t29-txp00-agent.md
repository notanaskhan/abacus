---
id: TASK-7521
title: T-05-T29 TXP-00 Agent tab, states A–E
plan_key: T-05-T29
spec: SPEC-651  # docs/screens/TXP-00.md
acceptance_criteria: [AC-1]  # all five artboards from fixtures with ink-2 spinners; running vs waiting without colour
risk_zone: green
status: in-review
branch: t05-t29-txp00-agent
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
TXP-00 a–e: rail (General Information, Links, Team), RunCard with six task groups and StatusDisc
rows, running/waiting/failed states, Run ⌄ (re-run task or group), ▶ Run in Idle, the chat-ask
QuestionCard for the §706(d) answer, Retry · Reconnect · View run, the composer handing off to
TAX-08.

## Plan
- `apps/web/src/screens/TXP-00/copy.ts`: the handoff's words (A–E), the six groups and ten rows
  (1 + 1 + 2 + 4 + 1 + 2 = 11 open), the §706(d) question (Reg. §1.706-4 options).
- `apps/web/src/screens/TXP-00/index.tsx`: `TXP00({frame, …intents})`, `rowState`, `openItems`,
  `frameOf(runs)`; running rows show an ink-2 spinner and "Running…", waiting rows a warn disc and
  "Waiting on 1 answer" (words and glyph, not colour alone); F-07's `QuestionCard` above the
  composer in D; the running pill in B.
- `routes/firm/tax-returns.tsx`: the entity layout's Agent tab mounts TXP-00 on the return's
  workbook runs (`GET …/workbook-runs`); the composer opens `?ov=assistant` (TAX-08).
- Test `TXP00.test.tsx`.

## Partial
- The rail's General Information values and the Links/Team rows read `GET …/general-information`
  (T-05-T06 stub, served by a later T-05 row); the band headings render. Live progress through the
  E6 RunStore lands with the workbook run (T-05-T31/T32): the frame follows the newest run's state.
- Gallery registration and parity (Tier D) ride T-05's screen-test row.

## Progress log
- `2026-11-12` — Built (DEC-4521). Tests run at the S39 end pass.
- `2026-11-12` — End pass (L2 copy): the handoff's "task" for a run step reads "step" (glossary: "Run step. Never task"): "Re-run this step", "10 of 10 steps", "3 steps running at once.", "Ready to run 10 steps". "▶ Run" is the play icon beside "Run" (L2 bans emoji). The handoff wording is otherwise verbatim.
