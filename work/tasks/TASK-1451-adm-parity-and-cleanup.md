---
id: TASK-1451
title: ADM-01/02/03 keyboard suites and cleanup; legacy people and walls and firm_settings.v2 retired (G-01-T17)
spec: SPEC-002
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: G-01
plan_key: G-01-T17
branch: s11-assurance
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Parity is locked and no legacy people or walls screen renders, with the flag retired in the Thu
Apr 1 batch."

## Plan
- Remove `/admin/people` and `/admin/walls`, delete `legacy/FirmPeople.tsx` and `legacy/Walls.tsx`;
  firm-menu rows and legacy links point at ADM-01/02/03.
- Retire their tests under DEC-594, following A-01-T21's DEC-442: each assertion mapped to the
  ADM-02 or ADM-03 test that carries it, new ADM tests where none did, retired behaviour named.
- Retire `firm_settings.v2`: registry entry, `make regenerate`, the settings contracts' gates,
  the flag-off tests converted, FE gates, fixtures, docs and journey notes.
- Keyboard suites for ADM-01, ADM-02 and ADM-03 (vitest, the P-06-T26 pattern).
- Not here: Tier C visual locking (a person's `pnpm visual` sign-off); Playwright.
- Rollback: revert the commit (the flag returns to the registry; set it on again per firm).

## Progress log
- 2026-10-27: built; DEC-594.
