---
id: TASK-7811
title: "Register the notices, reporting and platform workflows' work classes; guard every module's"
spec: SPEC-000  # fix (ADR-071)
acceptance_criteria: [AC-20]  # the guard test and the module suites pass
risk_zone: amber
status: in-review
branch: lo38-notices-work-classes
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Every workflow a module's api declares can be dispatched.

## Found
- Running the PF-X1 journeys locally, the worker failed to publish `notice.created` (LookupError), and `make seed-demo SLICE=notices` timed out on settle.
- notices registered none of its four workflows.
- reporting (FsDraft, TieOut) and platform (ReferenceSetFanOut) each had one or more declared but unregistered.

## Plan (amber)
- Call `register_work_classes(WORKFLOWS)` in the three apis.
- Guard test across every module the worker loads.
- No migration, no flag. Rollback: revert.

## Progress log
- 2026-11-12: built; the guard (82) and the notices, reporting and platform suites pass. The 4 WeasyPrint errors are this Mac's only.
