---
id: TASK-2406
title: K-02-T19 KNW-04 screen, parity, axe and journey tests
spec: SPEC-500
acceptance_criteria: [AC-13, AC-14]
risk_zone: green
status: in-review
epic: K-02
plan_key: K-02-T19
branch: s19-k02-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
KNW-04 screen and journey tests: a–i and j, loading, empty, error, not-allowed; the screen spec
with axe; journey steps J01-07, J05-S, J06 due dates and J10 thresholds; parity per artboard.

Acceptance: "All named tests pass in the fixture and staging projects with axe at 0 serious or
critical and a parity percentage recorded per artboard."

## Plan
Files: `apps/web/e2e/screens/KNW-04.spec.ts`; `apps/web/src/screens/KNW-04/knw04-states.test.tsx`;
`apps/web/e2e/journeys/{J01-firm-onboarding,J06-individual-1040,J10-month-end-close,J05-ssars}.spec.ts`;
`docs/design/parity-manifest.json` (KNW-04a–i, Tier C). The artboards' own unit tests exist
(KNW-04.test.tsx a–h, knw04-draft i, knw04-deadline j). Staging steps are `test.fixme` outside the
fixture project until the K-02 batch deploy; parity percentages are recorded once KNW-04 leaves
`planned` (DEC-195), which this task does not change.

1. [x] Screen spec with axe. 2. [x] C-20 states. 3. [x] Journey steps. 4. [x] Parity entries. 5. [ ] End review run.

## Progress log
- `2026-10-30` — Built on `s19-k02-t19` (build-only; tests run at the end review).

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; staging walk after the K-02 batch deploy.
