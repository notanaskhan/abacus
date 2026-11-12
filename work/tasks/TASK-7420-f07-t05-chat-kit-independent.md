---
id: TASK-7420
title: "F-07-T05: Independent AC tests for the chat kit and QuestionCard (ADR-078), written from the spec"
spec: SPEC-652
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: in-review
branch: s38-f07-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: F-07-T05
---

## Objective
Tests fail if an agent-owned element exposes Approve, Sign off, Release or Send, if agent text
bypasses AgentText, if a locked thread shows figures, or if a default answer is applied without an
explicit Skip.

## Plan (tests only)
`packages/ui/src/agent/chat/chat.ac.test.tsx` (6 pass), from SPEC-652 and F-07 §3 A–C against the
package's public exports (`@abacus/ui` index): no control in the frame, list, header or thread
starts with a human verb and no agent-owned element holds a control (INV-1); every agent sentence
sits inside AgentText or AgentBlocks; a person's words are never agent text; a locked frame or
thread shows no figure and no composer (INV-3); an open question's default is never applied by
time, blur or page hide; meta lines name people, never the agent as an owner (INV-5).

## Partial
- QuestionCard (F-07-T06, S39) does not exist yet: its keyboard model and "only an explicit Skip
  applies the default" are tested against the card when it lands; today's test holds the thread's
  half (nothing answers on its own).

## Progress log
- `2026-11-12` — Written (S38). 6 pass.
