---
id: TASK-2925
title: P-04-T58 parity, accessibility and keyboard for the 44 review-grammar artboards
spec: SPEC-000  # P-04-T58 row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T58
branch: s24-p04-t58
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-02
updated: 2026-11-02
---

## Objective

Every SHL-09/10/11/12/15/16 artboard (44) is measured by the parity harness, checked by axe and the keyboard suite; P-04's Tier C locks recorded; Tier D geometry for O1, O2, O3.

## Acceptance (backlog)

parity.json shows every artboard at or under 3% with the locked frames blocking, and axe reports zero serious or critical issues.

## Plan

- Contracts: `## Parity` tables in `docs/screens/SHL-09, 10, 15, 16.md`; new `SHL-11.md`, `SHL-12.md` holding only the parity rows (the full contracts are P-04-T60's). Locks: SHL-10 a/c/f, SHL-11 a/c, SHL-12 a/b/e, SHL-16 a/b.
- `docs/design/parity-manifest.json`: 44 `shl-*.window` entries (handoff PNG, sha256, crop window, Tier C, locks).
- Harness: `statesOf` reads prime keys (`ap`, `app`, `ep`); SHL-11 and SHL-12 join `BUILT_PLANNED`; `screen-parity.test.ts` asserts the 44 rows and the 10 locks.
- Gallery: SHL-11 registered (`/components/screens/SHL-11`), sheet for a–d, f–h and the 330 inline card for e.
- `apps/web/e2e/screens/SHL-review.spec.ts` (render + axe for 44; focus trap, Escape topmost and focus return, SHL-11 radio group); `apps/web/e2e/visual/tier-d-review.spec.ts` (O1 420, O2 480, O3 500 / top 52 / radius 14).

## Progress log

- 2026-11-02: built; not run (Playwright and pnpm at the S24 end pass). DEC-1970: locked Tier C stays report-only (chapter 04 §9.3; `gateOf` test) so "locked frames blocking" is open; C-25 Tier A chip crops are measured in the visual pass.
