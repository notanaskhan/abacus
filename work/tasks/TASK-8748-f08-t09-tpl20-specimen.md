---
id: TASK-8748
title: "F-08-T09: TPL-20 specimen states a-g (Granite Peak BH-FS-430, Sep 24 to Oct 1)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-f08t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T09
---

## Objective
TPL-20a to g render at their spec clocks with '40 rows · 1 exception', 0 adopted in a, and P CH / R HL locked on every row in e.

## Plan (green)
1. `apps/web/src/gallery/specimens/TPL-20/` (copy.ts, index.tsx): SheetLayout inside the T2 RecordCockpit (audit bar 59 · rail 330 · canvas 1036; dock 330), rows and strata from the F-08-T02 SURL seed, one scenario (clock, persona cole-hart) per letter a-g.
2. Register TPL-20 in `gallery/specimens/index.ts` for /components/screens/TPL-20?st=a…g.
3. Tests: `TPL20.test.tsx`, one per letter plus seed figures and the no-human-verb-on-agent check.
4. Rollback: revert the PR; gallery only, no backend.

## Progress log
- `2026-11-20` — Built, stacked on #2386; TPL-20 tests 10 pass, gallery + seed tests 100 pass, tsc and eslint clean. Deviations: the handoff folder isn't on this machine, so column headers follow the seed's field order and the copy comes from F-08 §2/§3; SURL-15 to SURL-40 are seed-derived counts only (DF-35), so the grid draws the 14 typed rows and SURL-27's 'edited by HL' in e waits on the backend scenario; SURL-05's two citations are built from the seed row's own fields. Parity and axe not run. Gates and tests run once at the S51 end pass (build first, test last).
