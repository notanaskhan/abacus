---
id: TASK-1484
title: Journey E2E and parity specs for ADM-06 and ADM-07 (G-02-T21; j01 2, j14 7)
spec: SPEC-349
acceptance_criteria: [INV-1, INV-2, INV-3, INV-4, INV-5]
risk_zone: green
status: in-review
epic: G-02
plan_key: G-02-T21
branch: s12-gov
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The two named Playwright journeys (j01 2: Felix in the security center; j14 7: the audit log
and its export) with INV-1 to INV-5 and axe, and the parity specs for ADM-06 a to h and ADM-07 a,
b, c, e, f, g.

## Plan
- `e2e/journeys/` specs in the existing journey style, fixture mode first, staging with real auth.
- Parity specs beside the existing parity suites (Tier C report, Tier D styles).
- Run locally with an untracked `apps/web/playwright.localbrowser.config.ts` (never committed).

## Progress log
- 2026-10-27: plan written.
