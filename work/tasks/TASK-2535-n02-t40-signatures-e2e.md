---
id: TASK-2535
title: N-02-T40 full-stack E2E for SIG-01, SIG-02, POR-06 and ENG-04, and j02 4/4c, j15 4, j16 7
spec: SPEC-381  # N-02 §10.1; docs/screens/{SIG-01,SIG-02,POR-06,ENG-04}.md
acceptance_criteria: [AC-13, AC-14]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T40
branch: s20d-n02-t40
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Full-stack E2E for AY's frontends: apps/web/e2e/signatures/{sig-01-hub,sig-02-builder,por-06-sign,
eng-04-letter}.fullstack.spec.ts and journey steps j02 4 and 4c, j15 4 and j16 7 with
assertInvariants and axeStep; fake provider in CI, demo account nightly.

Acceptance (backlog row): "The four specs and the journey steps pass nightly on staging with
INV-1 to INV-5 asserted and axe clean." Staging is out of this build (the user's scope: minus
staging).

## Plan (green)
- `e2e/signatures/*.fullstack.spec.ts` on the harness (axe and INV-1 to INV-5 after each step).
- Fixture wiring: `install-portal.ts` gains POR-06 (`/sign` on its own states); persona
  `owen-calder`. ENG-04, SIG-01 and SIG-02 walk their artboards (ENG-04's tab needs ENG-02's
  record around it, which its own scenarios do not serve).
- Journey blocks in `J02`, `J15`, `J16`.

## Notes
- SIG-01 has no route (`nav-areas` routed false) and SIG-02 opens as `?ov=envelope:<id>`: the
  fixture project walks their artboards; the hosted projects need seeded ids and the live letter
  routes (N-02-T35), so those steps are `test.fixme` with N-02-T42's owner (M13, S21). POR-06's
  list walks on the full stack too.

## Progress log
- `2026-11-01` — Written on `s20d-n02-t40` off main.
- `2026-11-01` — End review: the fixture project passes (20 passed, the files' existing fixme
  steps skipped). The SIG-02 f walk found an axe defect (a `<li role="alert">` unmade the list
  item); the alert moved to a span inside it.
