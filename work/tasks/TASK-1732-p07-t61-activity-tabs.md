---
id: TASK-1732
title: P-07-T61 Activity tabs on CLI-02 and ENG-02
spec: docs/screens/CLI-02.md; docs/screens/ENG-02.md
acceptance_criteria: [P-07-T61]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T61
branch: s14-p07-t61
created: 2026-10-28
updated: 2026-10-28
---

## Objective
CLI-02's and ENG-02's Activity tabs wired to P-07-T57's audit-trail lines. Acceptance (backlog
row): "Both Activity tabs render live lines with axe clean."

## Plan
- `apps/web/src/screens/shared/RecordActivity.tsx` (generated client, ADM-07's words).
- CLI-02 and ENG-02: the `activity` tab (production track), the fixture-build entry (DEC-822).
- Fixture handlers for both routes (empty page; no invented lines). Screen contracts amended.

## Acceptance
| Check | Test |
|---|---|
| Both tabs render live lines | `apps/web/src/screens/shared/RecordActivity.test.tsx` |
| axe clean | the gallery axe harness (Playwright) at the batch review |

## Progress log
- `2026-10-28` — Built. tsc, eslint, prettier clean. Tests written, not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** P-04-T33.
