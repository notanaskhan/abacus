---
id: TASK-8336
title: "W-01-T17: Connect flows"
spec: SPEC-659
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16]
risk_zone: green
status: in-review
branch: w01-t17-connect-flows
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T17
---

## Objective
Spec section: handoff WB-10, WB-11.
Connect flows.

## Plan (green)
1. `apps/web/src/screens/WB-11/flow.ts`: the Connect flow as a state machine (Enable → confirm → consent → provider → callback → connected; Reconnect at consent; fresh-MFA step-up first on a stale session; error and retry), `needsStepUp` (15-minute window); tests. WB-11 b (consent) and e (typed-name confirm) are W-01-T16's component.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. eslint, tsc and the WB-11 tests (11) clean while building. Partial: wiring the machine to WB-10's Enable, the `/workbench/connect/callback` route against the fake provider (W-01-T09's ConnectPort), the WB-10 confirm dialog and the live MFA step-up are not composed. Gates and
  tests run once at the S47 end pass (build first, test last).
