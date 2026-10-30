---
id: TASK-2110
title: T-01-T03 Consumer contract tests for the C19 and engine-bridge stubs
spec: SPEC-501
acceptance_criteria: [AC-9]
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T03
branch: s16-t01-t03
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Consumer suites for both T-01 stubs: TRI tags, no TIN, bank or CAF plaintext, one purpose per
consent document, status codes from the registry, no agent-holdable export, import approval or
transmission (T-01-T03).

## Plan
- `backend/tests/contracts/c19/test_c19_consumer.py`, `backend/tests/contracts/tax_engine/test_engine_consumer.py`.
- The TypeScript fixture assertions ride with T-01-T09, which builds the fixtures.

## Progress log
- 2026-10-29: written (S16 block; run at the batch's end review).
