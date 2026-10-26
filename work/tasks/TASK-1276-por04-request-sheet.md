---
id: TASK-1276
title: POR-04 request sheet frontend (R-01-T12)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T12
branch: s9b-portal-rooms
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"States a, b, c, d and g pass full stack, e and f render from fixtures with one primary button
each, and Esc returns focus to the invoking row." Screen POR-04 (docs/screens/POR-04.md), over
the live read model R-01-T07 (`GET /v1/portal/request-items/{id}`).

## Plan (green)
- `domain/portal/sheet.ts` (L3): the request and its shared thread over the generated client;
  upload (intent then the request's own upload), Ignore with a note, Undo, Withdraw, comment; the
  typed question and decision slots (`SheetQuestion`, `SheetDecision`) for C-01 and T-06 / T-09.
- `domain/portal/RequestSheet.tsx` (L3 composition): the O3 sheet with the request, question and
  decision variants, one primary each; the whole width at 390 (`SheetModal fullScreen`, a small
  additive kit prop) with "Take a photo" (the native camera input, DEC-45).
- `screens/POR-04/{index.tsx, scenarios.ts, copy.ts, POR-04.test.tsx}`; the portal route
  `/documents/requests/$requestId`; POR-03 rows open it (`RequestRow onOpen`, additive kit prop);
  the gallery's POR-04 artboards; fixture handlers for a comment and a request upload.
- No backend change, no new dependency.

## Progress log
- 2026-10-26: built. 14 tests in `POR-04.test.tsx` (a–g, the DF-15 Withdraw, a comment, an
  upload, Esc returning focus to the opener, a 404 reading "not available", 390). POR-03, the
  white-label lint, fixtures, routes and the Request kit and overlay suites still pass.
  The fixture's 1095-C size is 412 KiB (`412 * 1024`), so the portal's binary `bytes()` reads
  "412 KB" as the handoff shows. Not run here: the Playwright screen spec and axe (R-01-T21;
  local Playwright wants a browser build not cached), and the full-stack pass of a, b, c, d and g
  against a running stack. Deviations and the new words are in docs/screens/POR-04.md.
