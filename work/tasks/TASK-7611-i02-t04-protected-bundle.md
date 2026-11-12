---
id: TASK-7611
title: "I-02-T04 protected bundle: briefing matrix rows, today_brief.enabled, module dependencies"
plan_key: I-02-T04
spec: SPEC-654
acceptance_criteria: [AC-1]  # allow and deny tests; an agent context refused on all three; flag within its lifetime
risk_zone: red
status: in-review
branch: i02-t04-protected
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The Today brief's protected bundle: `briefing.read`, `briefing.rebuild`, `briefing.ask`; the
`today_brief.enabled` flag; `practice` may import `review`, `agents` and `requests`.

## Plan
- `permission-matrix/practice.yaml`: the three actions, every firm role allow; client roles,
  platform support, the agent and the system deny.
- `feature-flags/practice.yaml`: `today_brief.enabled` (default false, created 2026-11-12, expires
  2027-05-07 under DEC-137). HOME-01's "Open Today →" read this name already.
- `abacus_tools/quality/banned_patterns.py` `MODULE_DEPENDENCIES["practice"]` += review, agents,
  requests; `backend/pyproject.toml`: an import-linter contract forbidding review, agents and
  requests from importing practice.
- Regenerated `_matrix.py`, `_flags.py`, `actions.gen.ts`, the generated security tests.
- Test `backend/tests/unit/practice/test_i02t04_protected_bundle.py`.
- Rollback: revert; the flag is off and nothing calls the actions yet.

## Deviations (DEC-4610)
- The `daily_briefings` registry entries (TABLES, insert path) land with the table in I-02-T06,
  where the schema check can see them, not ahead of it.
- Flag dates follow the repository calendar (DEC-137), not the epic's 2028-05-04 to 2028-07-31.

## Progress log
- `2026-11-12` — Bundle built (DEC-4610). Tests run at the S40 end pass.
