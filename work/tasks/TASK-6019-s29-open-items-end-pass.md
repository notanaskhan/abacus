---
id: TASK-6019
title: "S29-open-items open items end pass: targeted gates, two fixes, status record"
spec: SPEC-000  # row (S29-open-items)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: S29-open-items
plan_key: S29-open-items
branch: s29m-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
One targeted gate run over #1396 to #1400 before the batch merge, and the round's status record.

## Plan
Gates: check-generated, ruff format and check, pyright (all of backend), lint-imports, error_codes, validate_docs, scope_guards, banned_patterns; unit suites for identity, methodology, review, evals, quality, api, review-grammar contracts, golden scenario, infra tests. Fixes: test_p04t17 narrows OpenGate.engagement_id (now optional, DEC-2613); test_portal_edge reads Vite's rolldownOptions (#1109 renamed it; a red on main). Status table in S29-blocked-and-rituals.md. Rollback: revert.

## Progress log
- 2026-11-08: built. 35,888 passed, 3 failed before fixes: two validate_docs tests (RB-61/RB-62 titles, fixed in #1396) and test_portal_edge (fixed here, 42 passed). Integration gate suites 45 passed earlier.

## Decisions made during this task
None.
