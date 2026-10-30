---
id: TASK-2313
title: K-02-T15 acceptance tests and I-CLOCKS golden fixtures for the calendar engine
spec: SPEC-500
acceptance_criteria: [AC-56, AC-57, AC-58]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T15
branch: s18-k02-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
AC tests for the reference-set service, CLI and calendar engine with the I-CLOCKS golden fixtures
transcribed into backend/tests/golden/calendar: TY2025 and TY2026 due dates, 990/8868, 706/4768,
5500/5558, AU-C 230 and 265, FTC +30, 8879 retention. Acceptance (row): every golden case passes
with its source citation and resolution returns the corrected version wherever one exists.

## Plan
- `tests/golden/calendar/i_clocks.yaml` (cited cases), `tests/golden/test_k02t15_calendar_golden.py`.
- Under the solo amendment ADR-078's split is void; written from the rules, not the engine.
- The CLI's tests ride K-02-T06 (#822); reference-set resolution ("a correction wins from its own
  effective date") is covered by K-02-T05's integration suite on 0400's resolver.

## Progress log
- `2026-10-30` — written; not yet run (S18 end review; `[skip ci]`).

## Handoff
- **Current state:** PR open, held.
- **Exact next step:** T-01-T18 final-approval guard (on K-02-T10).
