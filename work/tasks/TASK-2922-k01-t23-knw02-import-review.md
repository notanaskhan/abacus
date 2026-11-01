---
id: TASK-2922
title: K-01-T23 KNW-02 a, a2 and b import review on the T3 triad
spec: SPEC-600
acceptance_criteria: [K-01 §3.7 AC7.1, AC7.2, AC7.3]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T23
branch: s24-k01-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

KNW-02 shows a version made by an import: its uploaded files, the parsed steps with the page each cites, tracing both ways between a sheet row and its page region, the ⚑ flagged filter with Confirm, and the Parsing RunCard while the importer runs.

## Acceptance (backlog)

KNW-02a, a2 and b pass Tier C, and selecting step 4 lights page 14 while selecting the page region lights the row.

## Plan

- Backend (contract additive): `GET /v1/methodology/versions/{version_id}/import` (`imports.version_import`, READ, behind `methodology.import_review`); `StepOut.sources` from `program_step_sources` (`imports.step_sources`), each with a `match_id` (`step-<id>-p<page>`) both panes bind.
- FE: `screens/KNW-02/ImportReview.tsx` (`importViewerFile`, `ImportedStepRows`, `ParsingRunCard`); index wires the import query (2 s poll while parsing), MatchScope, Uploaded files group, SourceViewer, ⚑ Flagged tab (`flagged` search), Confirm through `flagResolutionMutation` (manage only, not once published).
- Fixtures: scenarios a, a2 (⚑ filter), b (1:51 PM, 41 of 96 pages); 3 flags (BH-EBP-110 step 7 split pp. 15–16, -310, -410); step 4 on p. 14.
- Tests: `apps/web/src/screens/KNW-02/KNW-02.import.test.tsx`; `backend/tests/integration/backfill/test_k01t23_import_review_triad.py`.
- DEC-1968 records what is deferred.

## Progress log

- 2026-11-01: built in abacus-s24; tests written, not run (build first, test last). `make generate` owed for `versionImportOptions` and `StepOut.sources` (end pass). Inline edit, the PBC links / Assertions sheet tabs and the 360 ms jump animation are not in this slice (DEC-1968).
