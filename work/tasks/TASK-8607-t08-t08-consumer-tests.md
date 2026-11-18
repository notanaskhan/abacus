---
id: TASK-8607
title: "T-08-T08: Consumer contract tests for the T-08 stubs and the contracts T-08 reads"
spec: SPEC-710
acceptance_criteria: [AC-37, AC-36, AC-20]
risk_zone: amber
status: in-review
branch: t08-t08-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T08
---

## Objective
Spec section: docs/plan/epics/T-08.md §8.2. Consumer tests for C21 (due dates), C19 (consent status), C3 (issue links, decision cards, checkpoints), C7 (draft envelopes) and T-02 engine summaries; provider checks on SS-1, FD-1 and TP-1.

## Plan (amber)
1. backend/tests/contracts/t08_practice/test_t08t08_consumers.py: classification on every model field, TRI on TP-1 figures and none on FD-1/SS-1, the slot kinds equal the FD-1 SourceKind literal, an unknown kind fails closed, the consumed fields exist on each provider model, 41 operations each with action and 501.
2. apps/web/src/fixtures/contracts/t08-practice.contract.test.ts: ENG-07 214 · 224 · 241, HOME-03 Sep 15 = 12, TAX-10 8 flagged and 7 of 8, each validated against the OpenAPI document.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5607). Not run: tests run once at the S50 end pass (build first, test last). Gates and tests run once at the S50 end pass (build first, test last).
