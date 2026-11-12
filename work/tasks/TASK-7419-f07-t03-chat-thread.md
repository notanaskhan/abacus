---
id: TASK-7419
title: "F-07-T03: ChatThread on the E6 RunStore: renderer registry for SessionItem kinds with consumer slots (approval, decision_ref, plan, run_card), Bubble me/line/block, InlineTable, FileArtifactRow, ChatErrorRow, NoticeRow, Composer, JumpFab, 20 ms client-side word reveal"
spec: SPEC-652
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
branch: s38-f07-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: F-07-T03
---

## Objective
Every agent string renders through AgentText or AgentBlocks, an unknown item kind renders a neutral
row and never raw payload, and reduced motion or ?static=1 shows verified text at once.

## Plan (amber)
- `packages/ui/src/agent/chat/thread.tsx`: `ChatThread` with the registry keyed by C6's eight
  kinds; `plan`, `question` and slot kinds (`approval`, `decision_ref`, `run_card`) through
  consumer slots, else the neutral row; `MeBubble` (a person's text), `LineBubble` (paragraph-only
  agent text through `AgentText`, revealed 20 ms a word when it arrives after the first render,
  whole under `still` or reduced motion), `BlockCard` (`AgentBlocks`: paragraphs, the inline table,
  kv, metric and file parts; the server's badge), `ToolCardRow` (agent_run_step states and the
  progress counters), `ChatErrorRow` (Retry emits the step once, View run the run), `FileArtifactRow`
  (Open · Download · Save to Files intents), `NoticeRow` (the server's words), `Composer` (Enter
  sends, Shift+Enter breaks a line, empty cannot send), `JumpFab` (when scrolled up and new items
  arrive), `role="log"` with `aria-live="polite"`; a locked thread renders nothing.
- `ToolCardRow` fills the P-09 gap logged in DECISIONS.md (F-07-T01).
- Tests `packages/ui/src/agent/chat/thread.test.tsx` (10 pass).
- Rollback: revert.

## Partial
- The question card itself is F-07-T06 (S39); the thread places it through `above` and the
  `question` slot. TPL-04's gallery page binding T04's fixtures to the thread is the S39 specimen row.

## Progress log
- `2026-11-12` — Built (S38). 20 vitest pass across the chat kit; tsc and biome clean.
