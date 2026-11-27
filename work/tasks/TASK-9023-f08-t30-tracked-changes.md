---
id: TASK-9023
title: "F-08-T30: Tracked-change marks, accept and reject intents, comment anchors (T20)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-f08-t30-tracked-changes
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: F-08-T30
---

## Objective
Backlog row acceptance: "Agent drafts enter only as tracked changes attributed '<person> via Agent', accept and reject fire only from a human click, and comments never disable Sign off."

## Done
- packages/ui/src/editor/changes.tsx: trackInsert (green ink, underline) and trackDelete (red ink, strike) marks with id, author, initials, time, viaAgent, client; a change-bar node decoration (2 px amber, initials, 'HL via Agent'); commentAnchor mark (amber tint and dot) whose click opens its C-29 thread (onOpenComment)
- Agent drafts: insertAgentDraft dispatches one transaction meta-marked as the agent's, and agentDraftPlugin refuses any agent transaction that inserts untracked text, deletes, or adds anything but a viaAgent trackDelete mark (INV-1)
- ChangeActions renders Accept and Reject only for a named person and fires only onAccept / onReject intents (the consumer applies them; P-35); openChanges and commentThreads reads; signOffBlockedBy reads review notes only, never comments
- Tests: src/editor/TrackedChanges.test.tsx (5); editor suite 15 pass

## Progress log
- `2026-11-27` — Built; 15 editor vitest pass.
