---
id: TASK-8930
title: "F-08-T24: Presence kit completion (C-28): PresenceStore, cell rings and labels, section editing banner, card presence, polling/SSE/scripted sources"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-f08t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T24
---

## Objective
Row acceptance: "Tints follow join order with the viewer excluded, idle over 5 minutes renders at 60%, and no presence state ever locks a cell, card or section."

## Done
- collab/presence: store (join-order tints, viewer excluded, idle 5 min, TTL 45 s), sources (polling, SSE, scripted with static), markers (cell ring + label, section banner, card stack, record stack), usePresence on useNow
- exported from @abacus/ui
- tests: presence.test.tsx (8)

## Progress log
- `2026-11-23` — Built; consumers mount markers (K-04 SHT/ENG-10, A-10 editor).
