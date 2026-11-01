---
id: TASK-2532
title: T-02-T28 independent AC tests for T-02-T17, T-02-T21 and T-01-T18's guard as T-02 uses it
spec: SPEC-502  # AC-1, AC-2; T-02 §3.3, §3.6
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: done
epic: T-02
plan_key: T-02-T28
branch: s20d-t02-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
ADR-078 independent AC tests for notanaskhan's red tasks T17 and T21 and for T-02's use of
T-01-T18's final-approval guard: five-layer human-only for k1_package.release, signer-only release
under BH-TAX-02, the Draft K-1 blocker T-02 registers and its clearing on release, staleness of
the TAX-02 approve control after a new import, Undo window, single-use grant, idempotent release,
duplicate void never on accepted evidence.

Acceptance (backlog row): "Tests written in ayushkbhatia's session from the SPEC and contracts
pass on main and fail on a planted agent approval."

## Plan (red: tests only, no product code)
- `backend/tests/integration/test_t02t28_k1_release_independent.py` on T-02-T21's harness and
  T-02-T19's duplicate upload: five layers (matrix, route, service, register, database; a planted
  agent or system release row and release of a package fail), BH-TAX-02 and final approval, the
  draft K-1 blocker cleared on release, Undo, single use, idempotency, duplicates and accepted
  evidence.
- `backend/tests/integration/test_t02t28_final_approval_stale.py` on T-01-T25's Feld harness: a
  new import blocks final approval, then the earlier checkpoint and hash are refused.
- Rollback: delete the two files.

## Progress log
- `2026-11-01` — Written on `s20d-t02-t28` off main; run in the end review.
