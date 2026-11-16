---
id: TASK-8323
title: "T-07-T24: 1041 K-1 release gate"
spec: docs/plan/epics/T-07.md F12
acceptance_criteria: [T-07-T24]
risk_zone: red
status: in-review
branch: t07-t24-1041-release-gate
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T24
---

## Objective
1041 K-1 release gate.

## Plan (red)
1. `tax/k1_release.py`: `gate_1041` (final approval AND a completed, not superseded `form_8879_f` envelope; the unmet steps in order); `eligibility` adds `form_8879_f` to a 1041's failing codes, so the release request answers 409 listing it.
2. Tests: `tests/unit/tax/test_t07t24_release_gate.py` (the truth table). Rollback: revert (the 1065 and 1120-S gates are unchanged).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5318). The app imports; the unit file ran green (6 cases). Partial: the K1ReleaseWorkflow's 1041 fan-out per recipient grant is T-02's existing per-package fan-out (unchanged); the DEC-85 drift void of the 8879-F, the TY2027 8879-F form-set row through the refdata CLI (human, per environment) and the `gate_unmet` response shape listing steps (the existing 409 names the failing codes) are not built. Gates and
  tests run once at the S47 end pass (build first, test last).
