---
id: TASK-8314
title: "A-08-T27: AUD-12 screen states a-h in fixture mode"
spec: SPEC-657
acceptance_criteria: [AC-0, AC-1]
risk_zone: green
status: in-review
branch: a08-t27-aud12-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T27
---

## Objective
Spec section: docs/specs/SPEC-657-a08-audit-fieldwork-depth.md F2, F3.
AUD-12 screen states a-h in fixture mode.

## Plan (green)
1. `apps/web/src/screens/AUD-12/`: `TestingWorkspace` (artboards a to h on the A-08 kit's boards and seed figures: JE testing, details Northwind, controls with the deviation log, agent testing, exception raised, expand sheet, awaiting approval, expand Northwind participants), `scenarios.ts`, `AUD-12.test.tsx`.
2. `screens/kit-a08.tsx` exports its JE board; `screens/gallery.tsx` registers AUD-12; `routes/manifest/aud.ts` marks AUD-12 `fixture` (no path of its own yet).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Prettier, eslint, tsc and the screen and kit tests (21) clean while building. Partial: the T2 template chrome, Review in package (fixture-only link), Open in Excel and the per-artboard acceptance-checklist parity run are not wired; the artboards compose the kit's boards directly. Gates and
  tests run once at the S47 end pass (build first, test last).
