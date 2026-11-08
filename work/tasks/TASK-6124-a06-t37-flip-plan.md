---
id: TASK-6124
title: "A-06-T37 A-06 flip: flags retired into the assurance_completion entitlement, migration 0713, RB-66 and RB-67"
spec: SPEC-000  # row (A-06-T37)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T37
branch: s30-a06-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-06 §4.9 and the row: flip plan, runbooks (assurance-completion and adjustments-flip), schema promoted before Dec 24, flags retired into the assurance_completion entitlement.

## Plan
- Migration 0713 on 0712: `assurance_completion` joins `tenant_entitlements`' modules; every firm with `assurance.completion` or `adjustments.entries` on gets its row.
- `platform/entitlements.py`: the module.
- `assurance/findings_contract.py`, `adjustments/contract.py`: the entitlement gate replaces each flag gate (404 without it).
- Flags removed from `docs/architecture/feature-flags/assurance.yaml`; `_flags.py` regenerated.
- AUD-16 (`Workbook.tsx`, its fixture): `useEntitlement('assurance_completion')`.
- The two flag-default tests now assert the flag is gone and the module exists.
- `docs/runbooks/RB-66-assurance-completion.md`, `RB-67-adjustments-flip.md`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff, pyright, eslint, prettier clean; the API client needed no change (entitlements are strings).

## Decisions made during this task
DEC-2714
