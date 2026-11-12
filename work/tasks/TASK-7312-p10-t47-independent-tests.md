---
id: TASK-7312
title: "P-10-T47: Independent AC and golden tests (ADR-078) for T27, T36, T42: topic authorisation, admin metadata-only topics, portal scope isolation, coalescing and backpressure, scenario goldens, ledger rounding and footing"
spec: SPEC-647
acceptance_criteria: [AC-T9, AC-T10, AC-M1, AC-M2]
risk_zone: amber
status: in-review
branch: s37-p10-t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T47
---

## Objective
Tests pass and fail if a portal principal receives a firm topic or a seed figure does not foot.

## Plan
- `backend/tests/unit/agents/test_p10t47_independent.py`, written from SPEC-647 (ADR-078 as
  amended, DEC-1668): a portal principal refused every firm topic; unknown kinds fail closed;
  `firm:home` and `user:<me>` only; the 500-event limit and the 100-topic cap; AC-M1 rounding as a
  property; AC-M2's 30-second boundary; the ADM-14a and ENG-06a seed rollups foot; stored minutes
  never drift in a rollup.

## Partial
- Admin metadata-only topics and the 250 ms coalescing need the stream's database path; the
  P-10-T27 integration suite covers them. T36's scenario goldens are the S35 export fixtures.

## Progress log
- `2026-11-12` — Written (S37). Run at the end pass.
