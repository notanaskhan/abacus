---
id: TASK-1113
title: Fixture scenarios screens/SHL-07 (a–e) and screens/SHL-08 (a–f, h) typed against C4, page PNG and region fixtures for the seven scenario documents, DF-31 words and copy (P-03-T07)
spec: SPEC-322
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9, AC-10, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18]
risk_zone: green
status: done
epic: P-03
plan_key: P-03-T07
branch: s7-p03-viewer
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"/components/screens/SHL-07?st=a-e and SHL-08?st=a-f,h render from fixtures at the 9:24 and 9:41 AM CT clocks with figures that foot" (P-03-T07).

## Plan
- `apps/web/src/fixtures/seed/trust.ts`: the C4 records (citations, manifests, regions, masks) typed with the generated `CitationV2Out`, `ViewerManifestOut`, `ViewerRegionOut`, `PiiMaskOut`; copy and figures from the SHL-07 and SHL-08 handoff specs and blueprint §9.4.
- `fixtures/handlers/trust.ts`: the C4 read routes (citations list and one, manifest, page PNG, regions, search) filtering as the server does (DEC-265).
- `fixtures/scenarios/SHL-07.ts` (a–e, Hannah, 9:41) and `SHL-08.ts` (a, c–f Samuel 9:24; b Hannah 9:41; h Hannah 2:30 PM; g is K-03's), re-exported from `screens/<ID>/scenarios.ts`.
- Footings in `fixtures/trust.foot.test.ts`; scenario tests in `fixtures/scenarios/SHL-0{7,8}.test.ts`.
- Gallery: SHL-08 drawn on the E5 shell (`screens/SHL-08/artboard.tsx`) until P-03-T14; SHL-07 with T11.

## Progress log
- 2026-10-24: built. Seven scenario documents (K-1 draft, K-1 statement, Ridgeline TB, Harborline, Claire's W-2, Halvard 1099, and the processing K-1), page images are the synthetic grey-rule PNGs the E5 specimens use (exported from `@abacus/ui/specimens`). The DF-31 status words already landed with the C4 stub (`citation`, `viewer`, `evidence_unlock` in the status vocabulary); "Unverified" (a boolean, not a status) is SHL-07 copy. No reveal handler: the reveal and its value are T16/T20. Tests: 21 fixture tests, 9 SHL-08 artboard tests. `docs/screens/SHL-07.md` and `SHL-08.md` (screen contracts) don't exist yet; the scenarios follow the handoff README artboard tables and P-03 §5.4.
- 2026-10-24: final checks on the branch: backend unit, contracts and security 26,387 passed (4 xfailed); integration (trust_kit, screening, access events, schema check, binder lifecycle, model foundation) 322 passed (2 xfailed); ruff, pyright, banned_patterns, validate_docs and error_codes clean; make check-fast green; apps/web vitest 1,488 tests, one SHL-01 timing test flaked under load and passes alone.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-268 | The SHL-07 container's open rules and the SHL-08 interim artboard | No |
