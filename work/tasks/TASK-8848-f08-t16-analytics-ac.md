---
id: TASK-8848
title: "F-08-T16: Independent AC tests for the analytics kit"
spec: SPEC-660
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-f08t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T16
---

## Objective
Tests prove restricted mode renders no name or link (INV-3), flag-off never 404s, no chart renders without a basis footer, and no peer-benchmark copy exists (D6).

## Done
- packages/ui/src/templates/analytics-kit.ac.test.tsx (ADR-078, independent of the builder's tests)

## Progress log
- `2026-11-20` — Solo edition (AMENDMENT-solo): the independent author is the same builder writing to the AC only, from the epic's text. Run at the end pass.
