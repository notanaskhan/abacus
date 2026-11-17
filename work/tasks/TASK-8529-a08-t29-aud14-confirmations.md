---
id: TASK-8529
title: "A-08-T29: AUD-14 confirmations screen states a-e"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
branch: a08-t29-aud14
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T29
---

## Objective
AUD-14 states a-e on T1 in fixture mode: filter chips, status tiles as filters, coverage line, grouped bank row, drawer with Response, Reconciliation, Classification and Why surfaced, manager-only Accept reconciliation, new confirmation sheet with address verification. AC: state e disables Send with the red helper and Accept reconciliation renders only for the manager role.

## Plan (green)
1. fixtures/seed/fieldwork.ts: GRANITE_PEAK_CONFIRMATIONS (C1 bank group with masked lines, C2-C4 AR) verbatim from the handoff; kit-a08-data re-exports
2. screens/AUD-14: scenarios a-e, copy, index (ConfirmationsWorkspace on the kit's ConfirmationDrawer and NewConfirmationSheet; RegistryStatus for the confirmation vocabulary; amount() for the coverage line), AUD-14.test.tsx
3. gallery registers AUD-14

## Progress log
- `2026-11-17` — Built; AUD-14 vitest 9 pass, tsc and eslint clean. Accept reconciliation is gated by the viewer's grants (the server's allowed_actions; no role compare, F-03-T32). SIG-02 authorization link and POR-17 preview wire in the live swap (A-08-T32). Gates and tests run once at the S49 end pass (build first, test last).
