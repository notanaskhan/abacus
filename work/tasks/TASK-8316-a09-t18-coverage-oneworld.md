---
id: TASK-8316
title: "A-09-T18: Connection coverage and OneWorld paths"
spec: SPEC-658
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
branch: a09-t18-coverage-oneworld
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T18
---

## Objective
Spec section: docs/specs/SPEC-658 F2.
Connection coverage and OneWorld paths.

## Plan (red)
1. `connections/coverage_routes.py`: `PUT /v1/connections/{id}/coverage` (`connection.manage_coverage`, a person authorised on an engagement of the connection's entity and of every entity named; 409 when another live ledger covers one).
2. `connections/netsuite_split.py` (pure): NetSuite's TB-by-subsidiary CSV split into one balanced trial balance per subsidiary; text never evaluated.
3. `connections/fake_oneworld.py`: the synthetic OneWorld connector (five subsidiaries, two periods), an expired token answers `needs_reauth` and is never retried; `pull_all`.
4. Tests: `tests/unit/connections/test_a09t18_oneworld.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5312). The app imports; the unit file ran green (4 tests). Partial: `ConsolidationPullAll` with child `RetrievalWorkflow`s and its replay history, the bulk-upload and pull-all routes (still 501), and A-02's reconnect request on Needs reauth are not built; the splitter and fake connector are their pure parts. Gates and
  tests run once at the S47 end pass (build first, test last).
