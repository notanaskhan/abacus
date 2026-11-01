---
id: TASK-2223
title: F-06-T12 independent AC tests for portal mobile (ADR-078)
spec: SPEC-000  # F-06-T12 row and docs/screens/TPL-19.md; no SPEC defines the specimen
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: done
epic: F-06
plan_key: F-06-T12
branch: s17-f06-t12
created: 2026-10-30
updated: 2026-11-01
---

## Objective
Independent acceptance tests (ADR-078) for the portal mobile specimen: hit areas, white label,
portal import boundary, Approvals hidden for households, axe at 390.

Acceptance (backlog row): "Tests prove 44 by 44 targets, no firm-shell imports in portal
specimens, no Accrued text or blue, and zero serious axe findings at 390 px."

## Plan
- `packages/ui/src/specimens/tpl19.ac.test.tsx`: import boundary over the portal mobile files
  (no toolbar, record header or cockpit, firm nav, screens or `@abacus/web`), with a non-vacuity
  guard; no "Accrued" or blue in any frame or in the kit sources; household nav and frame 7
  without Approvals; declared 44 heights on the capture kit's controls.
- `apps/web/e2e/screens/TPL-19.spec.ts` at a 390 viewport: axe on every built frame, measured
  44 × 44 targets, computed-colour blue check.
- Written from the row and the screen contract, not from F-06-T11's tests.

## Progress log
- 2026-10-30: written in S17 Lane 2 on F-06-T11; run in the end review.
- 2026-11-01: merged to main in #795 (aa98089e0).
