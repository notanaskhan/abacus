---
id: TASK-7411
title: "T-04-T40: TXI-02 K-1 treatment resolver states a-e in fixture mode on the T3 two-pane variant (876, 490)"
spec: SPEC-649
acceptance_criteria: [AC-7]  # AC-7.1 to AC-7.5
risk_zone: green
status: in-review
branch: s38-t04-t40
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T40
---

## Objective
TXI-02a-e render from scenarios, figures tie to 307,900, 16,025, 61,580 and 4,674,575, approval
collapses to the 10:24 AM checkpoint line, and the Draft chip stays until the released state.

## Plan
- `apps/web/src/screens/TXI-02/`: `copy.ts` (the handoff spec's copy and the Ridgeline K-1,
  verbatim), `Resolver.tsx` (K-1 card and chip cloud, the treatment table in the evidence grammar,
  the approval card, the PTET statement viewer; frames a–e; override with a required reason; the
  approve and override are the host's), `index.tsx`, `TXI-02.test.tsx` (13 pass).
- Gallery `registerScreen("TXI-02")` (a–e); the `/tax-returns/$returnId/k1-resolver/$activityId`
  route draws frame a in fixture mode.
- Rollback: revert.

## Partial
- The live host (reading `GET /v1/tax/returns/{id}/k1-activities`, approving through SHL-10 and
  the 10 s Undo) lands with T-04-T38's `k1_treatments` mode; the fixture screen is the contract.
- Links (TAX-05, TXP-12, TXI-03, SHL-08) stay handoff tooltips until the T-04 link wiring row.

## Progress log
- `2026-11-12` — Built (S38). 13 vitest pass; biome clean.
