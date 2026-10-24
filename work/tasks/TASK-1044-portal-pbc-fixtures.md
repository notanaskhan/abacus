---
id: TASK-1044
title: TS fixtures and scenarios for POR-03, POR-04 and POR-14 (R-01-T05)
spec: SPEC-323
acceptance_criteria: [AC-5]
risk_zone: green
status: done
epic: R-01
plan_key: R-01-T05
branch: s7-r01-portal-requests
created: 2026-10-24
updated: 2026-10-24
---

Plan of record: R-01 (docs/plan/epics/R-01.md §5.4); docs/screens/POR-03.md, POR-04.md, POR-14.md.

## Objective
"Every artboard opens from /components/screens/<ID>?st=<letter> and the footing tests pass against
the seed." Fixture handlers for the portal-pbc routes, the personas the three screens need,
per-artboard clocks and footing tests: 21 = 19 + 2 = Intake 2, 37 sorted, Keystone 4 of 9 then
5 of 9.

## What changed
- `fixtures/seed/portal-documents.ts`: the Feld binder from the request seed's seven rows (counts,
  category ticks and the Mark as Done state computed from the rows; 21, 19 and 37 are POR-02's
  `FELD_BINDER`), states a, c, c2, g and h; the drop batch (2 rule links + 1 waiting); Dana's
  bands for i; the 1095-C sheet for POR-04 with its thread; the question and decision slot data
  for POR-04 e and f (the §754 figures computed with integer arithmetic); Keystone's room at a, b,
  c and e and Harborline's at d, with the bridge-letter thread.
- `fixtures/handlers/portal-documents.ts`: the portal-pbc reads and the P-06 portal writes, in
  memory per scenario (Ignore and Undo, Mark as Done and Undo with a 409 on a second Undo,
  Withdraw with a 409 on an emailed file, upload intents, drops, the batch poll, the room, a
  code-only suggest, comments).
- `fixtures/scenarios/POR-03.ts` (12), `POR-04.ts` (7), `POR-14.ts` (6), each with an `ARTBOARD`
  map of what the client is doing at that instant (dragging, the Ignore popover, uploads in flight,
  390, the expanded room row).
- Personas: `ben-ashby`, `owen-calder` and `harborline-certifications` join the portal seed and
  `PORTAL_SHELLS`, with `dana-kowalski`'s shell. Harborline's contact is a `delegate` (request-item
  grants only, DEC-211), so the engagement's contact list is unchanged.
- `fixtures/portal-documents.foot.test.ts`: footings, every scenario's read valid against the
  OpenAPI document, every persona signed in, white-label and client words, and the writes.

## Decisions and gaps
- Only rows the handoff draws are itemized. The Feld binder's other 14 done requests count under
  Personal & Household Information until R-01-T11 names them; Dana's 4 undrawn requests and the
  file names behind POR-03 i's and POR-14's receipts (the handoff names none) also wait for T11.
  Those rows carry no file, so no Withdraw renders on them yet.
- "Opens from /components/screens": POR-03's artboards register in the gallery with R-01-T06;
  POR-04's and POR-14's with their screens (R-01-T12, R-01-T14). Until then the footing suite
  proves each scenario answers its screen's read.

## Progress log
- 2026-10-24: written; `vitest run src/fixtures` (270 passed), tsc, eslint, prettier clean.
