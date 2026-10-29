---
id: TASK-1817
title: Red-module coverage floors from S13 (Q-03-T066)
spec: SPEC-000  # chapter 10 row 2 and the Q-03-T066 row; no Q-03 SPEC defines coverage floors
acceptance_criteria: [AC-1]  # Q-03-T066: stage 2 fails a PR that drops any red module below its floor
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T066
branch: s13r-q03-t066
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Stage 2 fails a PR that drops any red module below its floor (97% line and 90% branch per red module from S13, beside the global `fail_under = 95`), thresholds in a protected file.

## Plan (red)
- `backend/coverage-thresholds.yaml` (protected, only raised): `line:` and `branch:` floors per red module (`abacus_tools.quality.mutation.SCOPES`).
- `abacus_tools/quality/coverage_floors.py`: default mode refuses a lowered or removed floor against `origin/main` (`make check-fast`, as `mutation_floors`); `--measure` reads `coverage json` after `coverage combine` and fails a red module under a floor (`make ci-coverage`, stage 2). A module with no measured file (`compute`) is not judged.
- Floors (DEC-907): measured baseline from main CI run 40849655921 (faf6d152), rounded down less one point; the target 97/90 is recorded and Q-03-T067 raises toward it.
- Tests: `tests/unit/quality/test_coverage_floors.py` (format, only-rise, measure and below).
- Docs: protected-paths "Only raised", DEC-907. Rollback: revert (the global floor is untouched).
- Not changed: the edit hook (`.claude/hooks/_protected.py`) guards only the mutation floors; CI is the enforcement for these (protected-paths: "CI is the enforcement").

## Progress log
- 2026-10-29: built; unit tests 12 passed; `measure` and `below` against run 40849655921's combined data: every module at or above its floor; the guard passes against origin/main.
