---
id: TASK-2638
title: T-01-T47 M11 go-live on PF-X1 (flip path, evidence pack, rollback)
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T47
branch: s21-t01-t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The pilot firm is live on the coordination layer at M11 with the evidence pack filed, and no T-01
flag expires between Sep 1 and Oct 20." Run on PF-X1 (DEC-1530), delta #2 waived (DEC-1680).

## Plan (amber)
- `OPS_COMMANDS` and `.github/workflows/ops-task.yml`: `abacus_tools.flags`, `abacus_tools.go_live`.
- `abacus_tools/go_live.py`: RB-18 and RB-19 join `SEASON_RUNBOOKS`.
- `backend/tests/security/test_tri_and_offshore.py`: the offshore fixture swaps the real C19
  registration and restores it (it errored since S21 batch 1: "already registered").
- `docs/ops/gates/M11-tax-coordination-PF-X1.md`: the flip runs, evidence, rollback; DEC-1680.
Rollback: revert; a flip already run is undone by the pack's §3.

## Human
- Dispatch the four flips on staging (ops-task, after staging carries this release) with the other
  founder as approver; paste the tax-level go-live check into the pack's §4.

## Progress log
- 2026-11-01: built; C19 42, I-7216/I-OFFSHORE 10, never-ERO 22, scrubbing 51 passed; allowlist and
  go-live tests 80 + 13 passed.
