---
id: TASK-2628
title: N-02-T43 parity and accessibility lock for SIG-01, SIG-02, POR-06 and ENG-04
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T43
branch: s21-n02-t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"parity.json lists every artboard with production states locked and axe reports zero serious or
critical issues." (N-02 §5.4, §5.5.)

## Scope
- `docs/design/parity-manifest.json`: 24 locked Tier C rows with the provider frame, signature
  images and DF-11 copy masked (DEC-1672).
- `apps/web/e2e/visual/tier-d-n02.spec.ts`: Alt+↑ document reorder and its live announcement
  (SIG-02 a), the provider frame's title (POR-06 b), POR-06 at 390, forced colours and reduced
  motion on all four screens.
- Axe on every scenario: the N-02-T40 screen specs (`e2e/signatures/*`) and the gallery screen
  specs already run it.
**Open (N-02)**: signer reorder and field placement by keyboard are not built; their test is
`test.fixme` naming the gap. SIG-02 b, c, d, g have no built artboard.

## Progress log
- 2026-11-01: written; runs at the batch's end review.
