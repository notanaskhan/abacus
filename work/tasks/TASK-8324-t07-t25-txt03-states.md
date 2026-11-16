---
id: TASK-8324
title: "T-07-T25: TXT-03 states in fixture mode"
spec: SPEC-656
acceptance_criteria: [AC-0, AC-9, AC-10, AC-11]
risk_zone: green
status: in-review
branch: t07-t25-txt03-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T25
---

## Objective
Spec section: handoff TXT-03.
TXT-03 states in fixture mode.

## Plan (green)
1. `apps/web/src/screens/TXT-03/`: `Beneficiaries` (A draft, B released, C elected, D ask the trustee, E empty) with the handoff's figures and words; `releaseEnabled` (both gate facts); tests.
2. Registered in the gallery; `routes/manifest/txt.ts` marks TXT-03 `fixture`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Prettier, eslint, tsc and the screen tests (7) clean while building. Partial: the live staging wiring to T-07-T23's read model, the composed a2/a3 frames, the O3 release confirm and Resend flows, SIG-02 and POR-13 links and the parity tier are not built. Gates and
  tests run once at the S47 end pass (build first, test last).
