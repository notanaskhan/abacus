---
id: TASK-2010
title: I-01-T14 HOME-01 MVP proof
spec: SPEC-385
acceptance_criteria: [I-01 MVP]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T14
branch: s15n-i01-t14
created: 2026-10-29
updated: 2026-10-29
---

## Objective
HOME-01 lite proven for M8: parity entries for a, a2, f and g (Tier C, the window crop), Tier D
geometry, axe and keyboard on every scenario, and the PW1 flip checklist.

Acceptance: "By Fri May 28, 2027 HOME-01 lite is parity-locked, axe clean and walkable on staging
with INV-1 to INV-5 asserted."

## Built
- `docs/design/parity-manifest.json`: `home-01{a,a2,f,g}.window` (Tier C, sha256 of the handoff
  PNGs). **Not locked yet**: the lock goes on per artboard once the end review measures each under
  the Tier C threshold (the S13 lesson: lock only what was measured).
- `apps/web/e2e/visual/tier-d-home.spec.ts`; `DashboardLayout` gains `data-dashboard="subbar"` and
  `"side"` hooks (no visual change).
- `apps/web/e2e/home/home-mvp.spec.ts`: axe and a Tab walk on all 14 scenarios.
- `docs/ops/pilot/pw1-home-flip-checklist.md`.

## Not done here
- "Walkable on staging": the journeys run once staging serves the app (S11 session's stand-up).

## Progress log
- 2026-10-29: built; specs written, not run (end review measures parity and locks).
