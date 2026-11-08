---
id: TASK-6230
title: A-05-T61 close, gallery artboards and parity baselines for A-05's 51 artboards
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T61
branch: s31c-a05-t61
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- `screens/gallery.tsx`:
  - `sectionArtboard`, the AUD-02 cockpit opened on a section and the state's options;
  - registers EBP-01 to EBP-09 and AUD-27.
- `AuditCockpitPage.initial` passes `accounts`, `estimatesRp`, `form5500` and `completion` through.
- `docs/design/parity-manifest.json`: 51 window entries; EBP-07a is locked.
- `e2e/parity/screen-rows.ts BUILT_PLANNED`: adds the ten screens.
- The screen contracts list each parity state.
- Test: `src/routes/screen-parity.test.ts` (51 rows, the EBP-07a lock).

## Left
- The staging walk of j03 12a/12b and j04 11 (no staging deploy).

## Progress log
- 2026-11-08: built; the artboards are measured at the close end pass.
