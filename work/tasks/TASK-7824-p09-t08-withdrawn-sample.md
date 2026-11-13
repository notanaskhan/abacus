---
id: TASK-7824
title: "P-09-T08 close: a withdrawn version never resolves as a step sample (test)"
spec: SPEC-000  # row P-09-T08
acceptance_criteria: [AC-1]  # visible-filtered samples
risk_zone: red  # evidence read path (test only)
status: in-review
branch: lo39-p09-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: P-09-T08
---

## Objective
#1821 (TASK-7808, DEC-4806) closed P-09-T08's open clause: steps record their samples and the
owning modules resolve them. Its security note left one predicate untested: a withdrawn evidence
version (ADR-162 §4) must never resolve, as a version or through its item.

## Plan
- `tests/integration/test_p09t08_trace_samples.py`: withdraw the world's only version; the step's
  samples keep the request item and the engagement and drop both evidence entries.

## Progress log
- 2026-11-13: written; runs in the lo39 end pass.

## Decisions made during this task
None.
