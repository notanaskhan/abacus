---
id: TASK-327
title: "F-05-T11: independent format.ts golden suite, 171 cited cases, DST change and relative dates"
spec: SPEC-048
acceptance_criteria: [AC-2]
risk_zone: amber
status: done
branch: worktree-agent-a57fa8250cb7338a9
worktree: agent-a57fa8250cb7338a9
created: 2026-10-21
updated: 2026-10-21
---

## Objective
An independent check (ADR-078) that `format.ts` follows the written formatting rules: expected values come from the plan and the handoff, never from the implementation.

## Scope
**In**
- `packages/ui/src/format.golden.test.ts`: table-form cases, each with a `cite` naming its rule.

**Out**
- Any change to `format.ts` or `clock.tsx` (a disagreement is reported, not fixed here).
- `format.test.ts` (F-05-T10's own tests) was not read.

## Context to load
- `docs/plan/04-frontend-architecture.md` section 3.7; `docs/plan/epics/F-05.md` section 3.B (B1).
- Handoff `_foundations/.../specs/05-data-formatting.md`; `packages/ui/src/tokens/DECISIONS.md` (the plan wins).
- Exported names and signatures of `format.ts` and `clock.tsx` only.

## Plan
Steps:
1. [x] Derive expectations from the sources: money (3 styles, parentheses, zero, half away from zero, 15 to 20 digits), percent and progress, masks, dates, times, date-times, relative dates, the Nov 1 2026 fall-back, the Mar 14 2027 spring-forward.
2. [x] Pin `now = 2026-09-14T09:24:00-05:00`, `tz = America/Chicago`; bind through `ClockProvider` and `useFormat()` for two cases.
3. [x] Run; keep every case that the spec supports; mark disagreements `it.fails` with `// F-05-T10 bug:`.

Tests to write (mapped to ACs):
- AC-2 (B1) -> `format.golden.test.ts`: 61 money cases (M01 to M61), 14 percent and progress, 9 mask, cellRef, viaAgent and SEP, 85 date, time, date-time, relative and DST, 2 clock-bound. 171 in all.

## Definition of done
- [x] `pnpm -C packages/ui test` (238), `tsc --noEmit`, `lint` and prettier pass.
- [x] Every case has a `cite`; the three named in the epic (`-0.004`, `0.005`, `-1234567.885`) are M39, M18, M19.
- [x] `format.ts` and `clock.tsx` untouched.

## New dependencies
None.

## Progress log
- `2026-10-21` - Wrote the suite from the spec. All 171 cases passed on the first run; no `it.fails` needed, no disagreement with F-05-T10.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Cases the sources do not state word for word say "inferred" in `cite` (calendar date has no time, explicit zero in `whole` and `cents`, "Today" for a calendar date) | Honest provenance; they follow from the stated rules | no |
| Left out: `since`, `period`, `longDate`, `monthYear`, `bytes`, `ratio`, `count`, `prose`, the `einMask` layout, `accountMask` with no institution | 04 section 3.7 names them but states no output rule, so any expected value would come from the implementation | no |
| Invalid money input passes if it throws or renders without digits | Spec says only "parsed exactly"; it does not say whether bad input throws | no |
| The 7-day cut-off to a short date is not tested at its edge | Handoff 05 calls it "an assumption"; R08 (3 Days Ago) and R09 (a month back) bracket it | no |

## Gotchas and discoveries
- The time-zone label is `shortGeneric`, so Chicago reads "CT" in both CDT and CST, including both passes of 1:30 AM on Nov 1.
- Hour-count traps for "Yesterday" across the fall-back day: S15 (26 hours, two calendar days) and S16 (24.5 hours, same calendar day).

## Questions for the human
- [ ] Should plan 04 section 3.7 state output rules for `since`, `period`, `longDate`, `monthYear` and the `einMask` layout so they can be golden-tested too?

## Handoff
- **Current state:** done; committed on this branch.
- **Exact next step:** none; F-05-T49 relies on this suite staying green.
- **Known failing checks:** none.
