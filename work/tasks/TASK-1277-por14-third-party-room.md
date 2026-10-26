---
id: TASK-1277
title: POR-14 third-party room frontend as the ScopedRequestRoom composition (R-01-T14)
spec: SPEC-323
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T14
branch: s9b-portal-rooms
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Six scenarios pass, the reduced toolbar offers only Requests, and full stack Sam cannot reach any
route outside the room." Screen POR-14 (docs/screens/POR-14.md) over R-01-T13's room read model.

## Plan (green)
- `domain/portal/room.ts` (L3): the room and the code-only suggest over the generated client; the
  person's upload, withdraw and comment on a delegated request (the sheet's calls).
- `domain/portal/ScopedRequestRoom.tsx` (L3 composition, A-09 reuses it for POR-23): the intro
  with "n of N uploaded", its bar and the "Drop files here" pill; folder bands with "n of N";
  rows with their sub-line and disc; an open row with the firm's guidance, files (Withdraw with
  the DF-15 words on the person's own unaccepted upload), the upload slot and the thread; the
  "Which request is this for?" picker with the server's pre-selection; the green banner.
- `screens/POR-14/{index.tsx, scenarios.ts, copy.ts, POR-14.test.tsx}`: T7 reduced with the one
  nav item Requests and the chip "Sam Ortiz · Keystone"; the 390 page with no tab bar; f for any
  404. Portal routes `/requests` and `/requests/$requestId`; gallery artboards a–f; fixture
  handlers for a request upload, a comment and a room withdrawal.
- `PortalLayout` draws no tab bar for an empty nav (an additive kit rule).

## Progress log
- 2026-10-26: built. 13 tests in `POR-14.test.tsx` (a–f, the reduced toolbar, an upload then
  Withdraw, the picker pre-selected by the suggest, a comment, expand and fold, 390). The server
  half of "Sam cannot reach any route outside the room" is R-01-T13's integration suite (every
  other portal read 404s to Sam); the full-stack walk and axe are R-01-T21's Playwright spec, not
  run here (local Playwright wants a browser build not cached). Portal, gallery, white-label and
  kit suites still pass.
