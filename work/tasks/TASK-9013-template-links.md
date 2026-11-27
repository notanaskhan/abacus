---
id: TASK-9013
title: "K-03-T19: Link semantics switch behind templates_v2.enabled"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-k03-t19-template-links
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: K-03-T19
---

## Objective
Row acceptance: With the flag off the existing SPEC-008 and roll-forward tests pass unchanged; with it on a second pin goes through template.apply_update only (the production-train clause is the batch merge's).

## Done
- pin writes the link beside the legacy column
- second pin answers 409 template_update_required
- pinned_version read by both roll-forward paths
- methodology wrapper reads exported
- acceptance tests plus SPEC-008 and roll-forward suites unchanged

## Progress log
- `2026-11-26` — 4 new tests and 44 existing SPEC-008 / roll-forward tests pass (48).
