---
id: TASK-2720
title: Q-04-T066 — extended on-call rota for the Sep 1 – Oct 20 window
spec: SPEC-402  # AC-3
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
epic: Q-04
plan_key: Q-04-T066
branch: s22-q04-t066
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The rota covers every day of the window with a primary and a named backup, and a test page
escalates correctly." Deadline-week double cover, quiet hours suspended in deadline weeks.

## Plan (red: ops rota, no code path to production)
- `docs/ops/on-call.md`: the `autumn-2027` window and its rota rows; a `Cover` column; rules for
  double cover. Rollback: revert the file (PW1's rows read as before).
- `abacus_tools.quality.on_call`: the deadline-week rules, read from `deploy/windows.yaml`.
- Tests in `tests/unit/quality/test_on_call.py`.

## Done (DEC-1771)
- All of the plan; SPEC-402 AC-3 extended. `make check-fast`'s on-call step passes on the
  committed file; `test_on_call.py` 19 passed; go-live suites 38 passed.

## Remaining (human)
- The test page: the paging tool (Q-01-T41) is not provisioned; recorded as not run.
- Both founders approve the rota (a swap or the publication is a PR both approve).

## Progress log
- 2026-11-01: built.
