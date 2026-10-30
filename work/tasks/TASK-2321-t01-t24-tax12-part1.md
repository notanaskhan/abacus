---
id: TASK-2321
title: T-01-T24 TAX-12 frontend part 1 (fixture mode)
spec: SPEC-501
acceptance_criteria: [AC-11]
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T24
branch: s18-t01-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
TAX-12 on the T2 cockpit in fixture mode: the nine-row checklist rail, OverviewCard, and the E-file
authorizations canvas (envelope card, packet, payments, gate, acks); states a, a2 and b.

## Plan
- `screens/TAX-12/{index.tsx,copy.ts,scenarios.ts,TAX-12.test.tsx}`.
- `fixtures/seed/tax/feld-delivery.ts`, handlers in `fixtures/handlers/tax-compliance.ts`,
  `fixtures/scenarios/TAX-12.ts`. docs/screens/TAX-12.md states; DEC-1367.

## Progress log
- `2026-10-30` — built (DEC-1367); vitest (5), tsc, eslint and prettier run once on the files.
  `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-02-T13.
