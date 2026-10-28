---
id: TASK-1852
title: K-01-T07 KNW-02 workbook slice (e, f)
spec: SPEC-345
acceptance_criteria: [K-01-T07]
risk_zone: green
status: in-review
epic: K-01
branch: s12r-k01-t07
created: 2026-10-28
updated: 2026-10-28
---

## Objective
KNW-02e and KNW-02f; Approve disabled with its tooltip while flags remain; a row problem shows
sheet, row and column but never the cell value.

## Built
- `screens/KNW-02/{index.tsx, copy.ts, scenarios.ts, KNW-02.test.tsx}` on `EvidenceTriad`
  (Prepare preset, embedded); route `/knowledge/methodology/$versionId` behind
  `methodology.lifecycle`; manifest path; gallery artboard.
- `domain/knowledge/methodologyUpload.ts` (upload and problem words).
- Fixtures: `handlers/methodology-versions.ts`, `scenarios/KNW-02.ts`.
- Contract stub `GET /v1/methodology/versions/{version_id}/programs` (DEC-957), `make generate`,
  the K-01 stub and route-introspection lists.

## Open
- The tree and sheet are fixture-only until K-01-T12 builds the program reads (S16).
- Tier C parity for e and f (not run).

## Progress log
- 2026-10-28: built; tests written, not run (end review).
