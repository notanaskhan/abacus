---
id: TASK-7509
title: F-07-T07 empty session, context picker and WB-06 agent detail
plan_key: F-07-T07
spec: SPEC-652  # AC-1 (T4f variant), AC-4 consumers
acceptance_criteria: [AC-1, AC-4]  # T4a, T4f, TPL-04b render from props; a prompt fills the composer without sending; the picker shows only L3's items
risk_zone: green
status: in-review
branch: f07-t07-empty-context
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
T4a's empty session (2 × 2 suggested prompts), the context chips row and the Paperclip context
picker (O1 380: Client record, Documents, Workpapers; loading and attached), and the WB-06 variant
(list 320, AgentDetail with the provenance chip, Pencil, Archive, dark Run).

## Plan
- `packages/ui/src/agent/chat/empty-session.tsx`: `EmptySession` (copy verbatim from T4a),
  `ContextChips`, `CONTEXT_KINDS`, `ContextItem`.
- `context-picker.tsx`: `ContextPicker` on F-05's O1 `Popover` (card, 380), rows only from
  `items`, `menuitemcheckbox` with the olive check when attached, spinner rows while loading.
- `agent-detail.tsx`: `AgentDetail` for WorkbenchLayout's `agent_detail` variant (F-07-T02 already
  narrows the list to 320).
- `thread.tsx` (S38 kit, not on a live path): `empty` (the thread's content with no items) and
  `draft` (`{text, nonce}`: fills and focuses the composer; only Enter or the send button sends).
- Tests `empty-context.test.tsx` (T4a prompts and T4f facts verbatim).

## Progress log
- `2026-11-12` — Built (DEC-4509). Tests run at the S39 end pass.
