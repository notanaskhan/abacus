---
id: TASK-6313
title: R-02-T13 Brightwater Hale portal slices and fixtures (POR-08, POR-09, POR-15)
spec: SPEC-646
acceptance_criteria: [AC-1]  # fixture data foots; seed and fixtures read one book
risk_zone: green
status: partial
epic: R-02
plan_key: R-02-T13
branch: s32-r02-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
The portal slice for approvals, deliverables and the governance room, from R-02-T08's figures book.

## Plan
- `apps/web/src/fixtures/seed/portal-r02.ts` (typed with the generated client), its foot test.
- Scenarios `fixtures/scenarios/POR-08.ts` (a, e) and `POR-15.ts` (a, n: Dana's management grant
  gets no room).

## Progress log
- `2026-11-09` — Built; not run (end pass). Partial: the backend seed (`make seed-demo`) does not
  yet write these rows, so the fixture/seed equivalence half waits for the seed writer; POR-09's
  drafts v3/v4 with the page-2 comment, the finals at release, the Copperleaf package screen and
  Meera's K-1 are data in the slice but have no scenario wired (POR-09 and POR-13 screens own
  them); `ben-ashby` and `victoria-lam` are new persona slugs to add to the personas registry.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3013 | One figures book for fixtures and seed; entry titles and lines from the book's groups | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
