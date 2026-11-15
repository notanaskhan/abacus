---
id: TASK-8029
title: "S44 main CI repair after the batch merge"
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # main's CI goes green on what S44 brought
risk_zone: amber
status: in-review
branch: s44-main-ci-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-15
updated: 2026-11-15
plan_key: S44
---

## Objective
Repair the CI failures S44's batch caused on main 17082f4be (CI 43650145936).

## Progress log
- `2026-11-15` — Built. The four failure groups and their fixes are in DEC-5018. Run locally: tests/acceptance 1,589 passed; security; test_schema_check_db; tests/unit and tests/contracts; web vitest 4,083 of 4,083; frontend gate.
- The `compute` coverage floor (100%) predates S43 and S44 (red since 61c47b52b) and is not touched here.
