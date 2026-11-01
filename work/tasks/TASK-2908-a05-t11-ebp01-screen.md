---
id: TASK-2908
title: A-05-T11 EBP-01 screen a-d (plan profile & service providers)
spec: SPEC-640
acceptance_criteria: [EBP-01 a-d]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T11
branch: s24-a05-t11 (stacked on s24-a05-t10)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

EBP-01 a-d as the AUD-02 cockpit's Overview › Plan profile canvas over A-05-T10's reads.

## Acceptance (backlog)

All four artboards render from fixtures and live data, and the EIN is never in the DOM, query cache or URL after re-mask.

## Plan

- `screens/EBP-01/PlanProfile.tsx`: `usePlanProfileCanvas` (Plan facts and Status & deadlines cards, Service providers table; b's missing-PN helper verbatim; c's EIN-ending note with Raise exception… and the TPA's Correction requested; d's edit mode with Save through `PATCH …/ebp/plan`); C-20 flag-off and walled states. AUD-02 selects it for `?section=ebp_01`; `planEditing` opens d.
- Fixtures: `fixtures/seed/ebp01.ts`, `fixtures/scenarios/EBP-01.ts` (a, b, c, d, off, not_allowed); `screens/EBP-01/{artboard,scenarios,copy}.ts(x)`.
- The rail row `ebp_01` goes `live`.
- Test `screens/EBP-01/EBP-01.test.tsx`: each artboard draws the server's figures; no nine-digit EIN in the DOM, the query cache or the URL.
- Not in this row (DEC-1955): the sponsor EIN's Reveal (logged) waits for A-05-T18's EIN capture (the row shows a dash); Invite provider… and Raise exception… render as controls whose writes land with A-05-T10's deferrals; SHL-08 at the adoption agreement clause waits for EBP-02's provisions (the checked-value link).

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-05-T10. The worktree has no node_modules: prettier, tsc and vitest run in the end review.
