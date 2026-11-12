---
id: TASK-7633
title: "S40 end pass: gates, tests, security review, one fix round"
plan_key: S40-end-pass
spec: SPEC-000  # sprint end pass
acceptance_criteria: [AC-20]  # make check-fast green; suites pass; one review and fix round
risk_zone: amber
status: in-review
branch: s40-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-13
updated: 2026-11-13
---

## Objective
One comprehensive pass over the 33 S40 PRs: regenerate, gates, full suites, security review, one
fix round, at most one re-review; then the batch merge with CI on this PR.

## Results
- `make check-fast` green, including the bundle budget at 140 KB per route (DEC-4628, founder).
- Backend: 57,872 unit/property/acceptance/contract and 11,367 integration/security/workflow
  pass, apart from `libgobject` on this Mac (WeasyPrint's system library; present in CI).
- Frontend: 1,374 kit and 3,930 app tests pass.

## Fixes (security review and gates)
- Search 429 raised `TypeError`; cell edit version check inside the write transaction; entity run
  plan levels now dependency depth (P-10 refused same-level dependencies); search resources from
  the engagement row; bound similarity setting; WF-001, BOUND-001, AGENT-001 gates.
- Registries, pinned lists and wiring for every S40 addition (details in the PR body).

## Progress log
- `2026-11-13` — End pass complete; re-review found nothing new.
