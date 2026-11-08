---
id: TASK-6115
title: "R-02-T06 portal shell hooks: /approvals, /deliverables, /governance stubs, the TCWG reduced nav, the K-1s target"
spec: SPEC-000  # row (R-02-T06)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: R-02
plan_key: R-02-T06
branch: s30-r02-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
R-02 §5.1: planned manifest entries and lazy route stubs for /approvals, /deliverables and /governance behind server-computed nav, TodoCard kinds for approvals waiting and deliverables ready, the TCWG reduced-nav model, the target of T-02's My K-1s banner; production output unchanged, fixture builds reach the routes.

## Plan
- `screens/POR-08`, `POR-09`, `POR-15/index.tsx`: lazy route stubs ("Not built yet" in fixture builds, nothing in production).
- `routes/portal/index.tsx`: lazy chunks; routes `/approvals`, `/deliverables`, `/deliverables/$deliverableId`, `/governance`, `/governance/$communicationId`; `PLANNED_AREA_PATHS` used by the nav only when `PLANNED_VISIBLE`.
- `domain/portal/shell.ts`: `GOVERNANCE_AREAS`, `governanceNav`, `isGovernanceScope` (a `governance_room` scope draws the reduced nav), `K1S_SECTION_TARGET`.
- `fixtures/contracts/portal-figures.test.ts`: R-02-T08's TS assertions over the figures book and POR-02's to-do words.
- `portal/r02t06-shell-hooks.test.ts`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). tsc shows no errors in the touched files; eslint and prettier clean.

## Decisions made during this task
DEC-2712
