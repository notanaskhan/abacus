---
id: TASK-2810
title: A-05-T04 contract stub ebp-workpapers v1
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T04
branch: s23-a05-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The stub merges dark behind ebp.modules with generated client types, and the
  contract doc lists every human-only action (verify, adopt, record correction, evaluate
  certification, conclude)."

## Plan (amber)
- `assurance/ebp_contract.py` (models with classification tags, gate, 33 routes; reads answer
  seed figures, writes 501), mounted in `assurance.api.ROUTERS`.
- Flags (3) and matrix rows (assurance.yaml) the routes need; `make regenerate` (matrix, flags,
  generated security tests, OpenAPI, client).
- `docs/contracts/ebp-workpapers.md`; `tests/contracts/a05_ebp/test_a05_stub.py`.
- Rollback: revert; flags default off.

## Progress log
- `2026-11-01` — built; ruff and pyright clean; `make regenerate` run. The plan's three-part
  action names were refused by the matrix (`entity.verb` only): renamed, DEC-1859. Tests at the
  S23 end review.

## Decisions made during this task
DEC-1859.
