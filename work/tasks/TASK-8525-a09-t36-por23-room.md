---
id: TASK-8525
title: "A-09-T36: POR-23 Component auditor room a–f"
spec: SPEC-658
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
branch: a09-t36-por23-room
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T36
---

## Objective
Spec section: docs/plan/epics/A-09.md §3 F6; handoff POR-23 a–f. ReducedPortalPage with one nav item, progress, Instructions band and acknowledge dialog, full-page letter reader with Download PDF, deliverable rows with DropZone and ambiguity picker, question composer and thread, Returned and Overdue pills, Invitation expired EmptyState, T7-M 390.

## Plan (green)
1. Screen `apps/web/src/screens/POR-23/index.tsx`: Overdue and 'Returned · not signed' pills, thread author · time, 'Open the full letter ›' reader with Download PDF (the instructions PDF route), DropZone (raw-body drop) and the 'Which deliverable is this for?' picker linking the drop, expired body with the firm's name; copy verbatim from the handoff.
2. Seed `fixtures/seed/group-audit.ts`: the handoff's four deliverables, states a–e, instructions §1–§4 and threads; handlers `fixtures/handlers/component-room.ts`; scenarios `fixtures/scenarios/POR-23.ts` and `screens/POR-23/scenarios.ts`.
3. Tests `screens/POR-23/POR23.test.tsx` (12: a–f, reader, picker, 390; no 'Accrued', no firm status words).
4. Also: the C-02 contract models are prefixed Posting*/W1*/Delivery* and the delivery hand-off routes renamed, because generic names (DecisionOut, ActivityOut, TalliesOut, HandoffOut, handoff_route) displaced existing generated-client exports.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5523). tsc and eslint clean; POR-23, AUD-35 and group-audit fixture tests 40 passed. Deviations recorded in docs/screens/POR-23.md. Gates and tests run once at the S49 end pass (build first, test last).
