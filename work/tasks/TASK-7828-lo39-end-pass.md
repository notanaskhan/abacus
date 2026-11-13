---
id: TASK-7828
title: "lo39 end pass: gates, tests, the security review and its fixes"
spec: SPEC-000  # end pass over TASK-7819..7827
acceptance_criteria: [AC-1]  # gates green, tests pass, review findings closed
risk_zone: amber
status: in-review
branch: lo39-endpass-fixes
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: F-01-T07
---

## Objective
One end pass over the lo39 stack (#1861 to #1883): gates, targeted tests, a comprehensive security
review (three subagents, as Ayush allowed for this step) and one fix round.

## Run on the stack tip (before fixes)
- `make check-fast`: 4 ruff errors in the Q-03-T179 sampler test (fixed here).
- Unit: 9,999 passed (touched modules and the new tests).
- Integration: 228 passed; the P-09-T08 withdrawn-version test failed (0144's guard: only a
  detached-key version, withdrawn as the session's own person; rewritten here, 4 passed); the
  schedules test failed on ordering in one shared Temporal server (passes alone, 5); the RB-18
  suites errored on fixture discovery in the combined run (alone: 10 passed, the rehearsal).

## Review findings and fixes (DEC-4821)
- High: stage 1 failed open on a crashed classifier; frontend-only and prose-only diffs skipped
  the secrets scan, generated-file drift, seed contamination, scope guards and quarantine.
- Medium: trace PDF renders uncapped; dark-merge audit gaps (existing flag flips, modified
  migrations, empty glob list, live-path coverage); two cut rows lost evidence.
- Low: ref option injection in the audit; PDF missing-glyph; audit event lacks the source digest;
  SIG-01 spec robustness (labelled checkboxes, tablist role, an annotation for the skipped state).

## Progress log
- 2026-11-13: fixes built; their unit tests pass (trace PDF 12, audit 16, stage 1 5, T179 44,
  P-09-T08 integration 4).

## Decisions made during this task
DEC-4821.
