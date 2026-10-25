---
id: TASK-1228
title: T9 QueueDetailLayout with the C-17 Issue kit (F-05-T55) and T8 InboxLayout with the C-15/C-18 File kit (F-05-T56)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T55; F-05-T56
branch: s8b-admin-kit
created: 2026-10-25
updated: 2026-10-25
---

## Objective
F-05-T55: "T9a to T9e render all three presets with Why This Was Surfaced on an olive disc, and the
agent can be assigned but is never offered Resolve."
F-05-T56: "T8a to T8e render the four dot states exactly, ignored rows go ink-3, and Match client
appears as an amber-ink chip."

## Scope
**In (F-05-T55)**
- `packages/ui/src/issues/issue-kit.tsx` (C-17): `IssueQueue` (tree, severity, radio; ↑ ↓),
  `IssueDetail` (key-value rows with the assignee picker, What it blocks, Workbook cells and Linked
  Entities that light their source, Why This Was Surfaced on the olive disc, the agent's
  explanation and run line through `AgentText`, the empty card), `IssueFooter` (a person's verbs
  only; nothing for an agent actor, INV-1), `IssueComposer`.
- `packages/ui/src/templates/queue-detail.tsx`: `QueueDetailLayout` on the C-09 presets
  `issues-individual`, `close-review`, `issues-entity`, one MatchScope.
- `packages/ui/src/specimens/t9.tsx`, `t9-data.ts`: `t9-queue-detail`, artboards `t9a` to `t9e`
  (the T9 handoff's issues; DEC-354 for the Ridgeline names).
- Parity `t9-queue-detail.t9a` to `.t9e` at Tier B; Tier D panes.

**In (F-05-T56)**
- `packages/ui/src/inbox/inbox-kit.tsx` (C-15/C-18 inbox visuals): `InboxDot` (the four states
  exactly), `InboxRow` and `InboxList` (threads, children indented 34, ignored rows ink-3),
  `ClientMatchChip` ("Match client…" in amber ink), `ReadingHeader` (File… or Move…, Ignore,
  Reply), `MessageView`, `AttachmentThumb`, `AgentFilingNote` (AgentText, Review only).
- `packages/ui/src/templates/inbox-layout.tsx`: `InboxLayout` (filter bar 50 −10, the C-09 `inbox`
  preset, panes 752 tall).
- `packages/ui/src/specimens/t8.tsx`, `t8-data.ts`: `t8-inbox`, artboards `t8a` to `t8e` (the T8
  handoff's inbox with the seed's names; DEC-354).
- Parity `t8-inbox.t8a` to `.t8e` at Tier B with a deviation; Tier D rail and rows.

**Out**
- TPL-09 (F-05-T57) and TPL-08 (F-05-T58): the seed's issue lists and the firm Inbox specimen.

## Definition of done
- [x] F-05-T55: 11 tests in `templates/queue-detail.test.tsx`; tsc, eslint, prettier for `packages/ui`
- [x] F-05-T56: 8 tests in `templates/inbox-layout.test.tsx`; tsc, eslint, prettier for `packages/ui`

## Progress log
- 2026-10-25: F-05-T55 built. Decisions in `tokens/DECISIONS.md` (F-05-T55) and DEC-354.
- 2026-10-25: F-05-T56 built. Decisions in `tokens/DECISIONS.md` (F-05-T56); DEC-354 extended to T8.
