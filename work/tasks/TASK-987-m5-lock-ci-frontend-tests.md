---
id: TASK-987
title: M5 lock of DS tiers 0 and 1 at Tier A, D and B, and independent AC tests for the CI frontend job (F-05-T49, F-05-T62)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-6]
risk_zone: red
status: done
epic: F-05
plan_key: F-05-T49; F-05-T62
branch: f05-t49-t62-m5-lock-ci-tests
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- F-05-T49: "the listed frames are parity-locked at the recorded tier and axe AA clean, the lock
  cites the Decision Day parity-tier record, and every deviation and mask is logged in
  DECISIONS.md."
- F-05-T62: "Tests written in AY's session prove a frontend-only diff skips backend shards, an
  over-budget firm, portal or route chunk fails, and each compiled-CSS rule rejects its deny case,
  and they pass unedited on main."

## Plan (red: T62 tests the protected CI wiring; nothing in `.github/` changes)
- **Files.** `docs/design/parity-manifest.json` (`locked: true` on 49 frames; TPL-18's
  deviation dropped), `apps/web/e2e/visual/support.ts` (`shootWhole`) and `parity.spec.ts` (frames
  shot at their exact box), `tier-d.spec.ts` (T11, T12, O6 geometry). T11/TPL-11 geometry tuned to
  the canvas (`dashboard-layout.tsx`: tiles 99 at radius 14, KPI 22/400, fixed deadlines pane,
  columns gap, compact T11 rows). Specimen toolbars use `moreFirst`, as the app's does.
  T62: `backend/tests/unit/tools/test_f05t62_ci_frontend_independent.py`,
  `apps/web/src/lint/f05-t62-ci-frontend.test.ts`; `backend/pyproject.toml` gives the new test
  file the same S603 allowance as `test_paths.py`.
- **Decisions.** DEC-192 (the parity-tier reading, recorded under AMENDMENT-solo since TASK-119's
  Block C has not written it) and DEC-193.
- **Rollback.** Revert the commit: the manifest loses its locks and the harness its exact-box shot.

## Scope
**Out (reported, not done)**
- T1 and O1 to O6 frames: no framed specimens to compare, so no entries to lock.
- T2a to e, T7-M, TPL-07-M, TPL-15c and j, TPL-11b: over Tier B or carrying a recorded deviation.
- The four `c-06-status-disc` Tier A failures: they fail on main too (the element-shot path this
  task leaves alone); not masked.

## Definition of done
- [x] Parity: 49 locked frames pass Tier B locally (0.16 to 2.00 %); Tier D 39 of 39
- [x] axe over every specimen, forced colours, keyboard and target size; INV sweeps
- [x] T62: 13 pytest cases and 12 Vitest cases green
- [x] packages/ui and apps/web vitest, tsc, eslint, prettier; bundle budget

## Progress log
- 2026-10-23: built. Parity baselines are cropped locally from the handoff; CI has none, so the
  locks bind wherever `pnpm visual:baselines` has run. The lock margin is thin on T7a, T7b, TPL-07b
  (1.99 to 2.00 %) and TPL-18a (1.98 %).
