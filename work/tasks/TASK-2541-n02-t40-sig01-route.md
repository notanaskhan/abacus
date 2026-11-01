---
id: TASK-2541
title: "N-02-T40 prerequisite: route SIG-01 at /signatures"
spec: SPEC-381  # docs/screens/SIG-01.md route and params
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T40
branch: s20e-sig01-route
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
N-02-T40's `sig-01-hub.fullstack.spec.ts` needs the hub reachable; the Signatures area was
`routed: false`.

## Plan
- `routes/firm/signatures.tsx` (flag `signatures.envelopes`, the contract's search), the area's
  routes, `nav-areas.ts` routed, manifest path; SIG-01 opens a drawer by id too (DEC-1582).

## Progress log
- 2026-11-01: built; routes, app-core, SIG-01 tests pass except link-contract's AUD-11 → AUD-07,
  red on main already. Status stays planned until the five designed links are wired.
