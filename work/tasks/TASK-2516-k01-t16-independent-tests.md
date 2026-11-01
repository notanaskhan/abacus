---
id: TASK-2516
title: K-01-T16 Independent AC tests (ADR-078) for K-01-T12 and T14
spec: SPEC-008  # K-01 §3.4 and §3.5 acceptance criteria
acceptance_criteria: [AC-1]  # and K-01 §3.4, §3.5
risk_zone: amber
status: done
epic: K-01
plan_key: K-01-T16
branch: s20b-k01-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Independent AC tests (ADR-078) for T12 and T14: published-version immutability, step_key
stability across drafts, QM-only mandatory changes (INV-1), verifier accept and reject (INV-2),
export determinism, walls on the cited-by list (INV-3).

Acceptance (backlog row): "Every amber AC in sections 3.4 and 3.5 has a passing test written in
N's session."

## Plan (amber)
- `backend/tests/integration/backfill/test_k01t16_independent.py`, from K-01 §3.4 and §3.5 and
  the matrix, reusing only K-01-T05's synthetic workbook builders.
- Fix what the suite finds, in its own change: AC4.6's `methodology_version.exported` audit event
  was never written (`methodology/programs.py`).
- No migration, flag or registry edit. Rollback: revert.

## Not covered (open)
- AC4.7 "Where step 4 is cited" filtered by visibility (INV-3): no route lists a step's citations
  on main (C4 has no by-source query). Belongs with K-01-T15's dock and a C4 addition.
- AC4.1, AC4.2, AC5.1, AC5.5, AC5.6 are frontend frames (K-01-T15, K-01-T17).
- AC5.4 answers 409 `stale_version`, not the epic's 412 (DEC-1361); the T14 suite covers it.

## Decisions
DEC-1564.

## Progress log
- `2026-10-31` — Built on `s20b-k01-t16` off main 7d4def8e5. The suite found the missing export
  audit; fixed. K-01-T12, T14 and T16 suites: 15 passed.
