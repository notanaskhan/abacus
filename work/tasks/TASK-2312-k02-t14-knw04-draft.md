---
id: TASK-2312
title: K-02-T14 KNW-04i draft and publish
spec: SPEC-500
acceptance_criteria: [AC-52, AC-53, AC-54, AC-55]
risk_zone: green
status: in-review
epic: K-02
plan_key: K-02-T14
branch: s18-k02-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
KNW-04i: New version…, typed editors per kind, amber-tint changed cells with struck prior values,
sticky Save bar with effective date, Publish vN… ConfirmDialog with fresh-MFA step-up, Discard
draft, 409 handling, Import… and Export from allowed_actions. Acceptance (row): KNW-04i matches
its artboard, non-owners never see Publish, and a stale draft shows the Changed by … reload row.

## Plan
- `screens/KNW-04/draft.tsx`, wiring in `index.tsx`, copy; fixture draft store in
  `fixtures/handlers/standards.ts`; scenarios `i`, `i_stale`; screen contract note (D7).
- Tests: `screens/KNW-04/knw04-draft.test.tsx`. Parity and axe: K-02-T19.

## Progress log
- `2026-10-30` — built (DEC-1359). Tests written, not yet run (S18 end review; `[skip ci]`).
  Import… upload control not drawn yet (the raw-body import route is K-02-T11's, #825); Export is.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** K-02-T15 tests; then T-01-T18.
