---
id: TASK-7503
title: P-02-T03 SHL-02 screen contract
plan_key: P-02-T03
spec: SPEC-000  # screen contract
acceptance_criteria: [AC-1]  # seven artboard states, the e deviation, the clock decision, every outbound target
risk_zone: green
status: in-review
branch: p02-t03-shl02-contract
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Write `docs/screens/SHL-02.md` from the handoff (README, spec, R2 revision) and P-02: states a–g
with persona, clock and parity tier, the DEC-43/DF-14 deviation for e, the canonical group order,
copy keys, outbound targets with their status, and the AVOID list.

## Plan
- `docs/screens/SHL-02.md`.
- `apps/web/src/routes/p02-screen-contract.test.ts`: the seven letters, the e deviation, the clock
  decision, the group order, and every outbound target (the spec's INTERACTIONS; the canvas link
  graph holds none for SHL-02) is in the Links table and the manifest.

## Progress log
- `2026-11-12` — Contract written (DEC-4503). OQ-3 (group order), OQ-4 (platform key caps) and
  OQ-6 (clock) settled with P-02's recommendations; OQ-2 (no new navigation group) recorded.
