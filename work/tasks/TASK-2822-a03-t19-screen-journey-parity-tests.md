---
id: TASK-2822
title: A-03-T19 screen, journey, parity and axe tests for AUD-11, AUD-31 and SHL-14 c
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T19
branch: s23-a03-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "All four journey slices pass on staging with axe clean, and the parity manifest
  shows every A-03 artboard built, locked or recorded as deferred."

## Plan (green, tests and parity records)
- **Screens** `apps/web/e2e/screens/A03-sampling-mapping.spec.ts`: every AUD-11 and AUD-31 scenario state.
  - Each state renders with axe at zero serious or critical findings.
  - A keyboard path checks the actionable states.
  - AUD-11 b keeps Generate disabled.
  - AUD-31 e′ says "Changed after sign-off".
  - SHL-14 c joins `SHL-14.spec.ts`.
- **Journeys** `apps/web/e2e/journeys/A03-sampling-mapping.spec.ts`:
  - j03 11: AUD-11 b → a → c, then SHL-14 c.
  - j04 2: AUD-31 f → e′.
  - j22 2's sampling slice: AUD-11 f.
  - All three run in the fixture project. Hosted walks are `test.fixme` with their owner.
  - j20 3's contract slice is `test.fixme`: it is API-level on the Harlow & Pike-shaped entity, on the full stack.
  - The harness gains Caleb Dunn and Simone Baptiste.
- **Parity:**
  - The contracts' `## Parity` tables cover AUD-11 a–f (Tier C; a and f locked), g for X-01, and host D.
  - They cover AUD-31 f (C, locked), a2–e2 (D) and a–e for A-09.
  - The manifest gains `aud-11a`–`aud-11f.window` and `aud-31f.window`, pinned to the handoff PNGs (`crop_handoff --pin`). The dock pane is masked.
- **Human:** the staging walk.
- Rollback: revert.

## Progress log
- `2026-11-01`: written; prettier, eslint and tsc clean. The specs run in the end pass (build-first rule). The staging walk is human.

## Decisions made during this task
None.
