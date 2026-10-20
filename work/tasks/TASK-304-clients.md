---
id: TASK-304
title: "Clients index and client record"
spec: SPEC-303
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: green
status: done
branch: task-304-clients
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- `organisations.names_of` also returns the client id.
- `ClientNames` and `EngagementView` carry `client_id` and `client_entity_id`.
- `EngagementSummaryOut` gains both fields.
- Web:
  - `screens/Clients.tsx` (groupClients, Clients, ClientRecord);
  - routes `/clients` and `/clients/$clientId`;
  - a toolbar link and the palette's Clients group.

## Definition of done
- [x] `spec303clients.test.tsx`, the palette, Engagements, Board, Layout and router tests, and the engagements and organisations unit tests pass; check-fast passes.

## Progress log
- 2026-10-20: built and merged.
