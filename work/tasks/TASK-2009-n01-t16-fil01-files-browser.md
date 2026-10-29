---
id: TASK-2009
title: N-01-T16 FIL-01 Files browser and document drawer (fixture)
spec: SPEC-380
acceptance_criteria: [Story 7]
risk_zone: green
status: in-review
epic: N-01
plan_key: N-01-T16
branch: s15n-n01-t16
created: 2026-10-29
updated: 2026-10-29
---

## Objective
FIL-01 a–j on the T2 tree · list frame with the O2 drawer, read-only (DV-10), over fixture
scenarios in the Files read model's shapes (N-01-T19), through the generated client. Routes
`/files` and `/files/$clientId` with `?node=&doc=` deep links behind `files.browser`.

Acceptance: "Ten scenarios render, no write control appears, and the virtual statements foot to
512,400."

## Built
- `screens/FIL-01/{index.tsx,copy.ts}`: tree (counts, Other clients band), list (folder band with
  the server's count line, evidence table, virtual children, superseded struck), hold banner,
  sealed archive pill, drawer (R2 control row with read-only P/R slots and client access; Document
  with the masked TIN and a 10 s logged reveal; Virtual documents with the server's tie total;
  Linked to; Versions; Access log; Retention), processing state, empty folder.
- `fixtures/seed/files.ts`, `fixtures/scenarios/FIL-01.ts`: ten scenarios (e, h, i, j fixture-only).
- `routes/firm/files.tsx`; FIRM_AREAS Files; manifest FIL-01 `fixture` at `/files`.
- Gallery `/components/screens/FIL-01?st=a…j`.

## Not done here
- CLI-02's Files tab stays a planned tab: it links to `/files/$clientId` once N-01-T23 swaps FIL-01
  live (the tab's planned/visible switch belongs to that swap).
- The reveal is a callback: N-01-T23 wires it to P-03's `pii-reveals` for the version's TIN region.

## Progress log
- 2026-10-29: built; `FIL-01.test.tsx` written (all ten render, no write control, 512,400 tie,
  c/d/f/g), not run yet (end review). tsc and eslint clean.
