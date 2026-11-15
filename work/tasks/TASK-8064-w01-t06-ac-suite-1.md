---
id: TASK-8064
title: "W-01-T06: ADR-078 AC suite 1 plus C20 v2 consumer contract tests"
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2, AC-4, AC-5, AC-6, AC-7, AC-8, AC-12, AC-17, AC-24, AC-26, AC-31, AC-32, AC-34]
risk_zone: amber
status: in-review
branch: w01-t06-ac-suite-1
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-01-T06
---

## Objective
AY's independent suite over N's red Connect work, failing against the 501 stubs where the services
are not built, and the consumer tests that run in N's CI now.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Written (DEC-5049). ruff, pyright and banned_patterns clean on the new files.
- **Partial:** AC-9 to AC-11, AC-17 to AC-23, AC-25, AC-32, AC-33, AC-35 move to suite 2 with
  their services. The strict xfails here are removed in the change that implements each.
- **End-pass note:** a repo-wide banned_patterns run on this stack shows ANY-001, TYPE-001 and one
  BOUND-001 (`granite_peak_gl.py` imports `sampling.compute`; export through `sampling.api`) in
  earlier S45 files; they belong to the fix round.
