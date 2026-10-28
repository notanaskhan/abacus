---
id: TASK-1604
title: Firm-intake consumer contract tests (N-01-T03)
spec: SPEC-380
acceptance_criteria: [AC-4, AC-5, AC-10, AC-18, AC-22]
risk_zone: amber
status: in-review
epic: N-01
plan_key: N-01-T03
branch: s13-ready
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The stub's guarantees and the shapes R-01, T-02, I-01, P-11, N-02 and A-07 build against, as tests.

## Plan
- `backend/tests/contracts/firm_intake/test_n01_stubs.py`: one action per route; firm routes client 404 → action → flag 404 → 501; portal routes firm 404 → flag → 501; ADR-031 classification; INV-1 human-only writes; INV-4 `scope_only`, no third party; DV-11 metadata deny for clients and the agent; consumer shapes (client words, waiting counts, six inbox states, five folder kinds, identifier-only facts, masked TIN).
- TS fixture assertions follow with the fixtures (N-01-T11, T15, T16).
- Rollback: revert.

## Progress log
- 2026-10-27: written; run in the end-of-batch targeted pass.
