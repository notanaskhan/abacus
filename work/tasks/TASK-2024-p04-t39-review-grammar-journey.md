---
id: TASK-2024
title: P-04-T39 API-level review grammar journey
spec: SPEC-360
acceptance_criteria: [AC-10]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T39
branch: s15n-p04-t39
created: 2026-10-29
updated: 2026-10-29
---

## Objective
`backend/tests/integration/review/test_review_grammar_journey.py` over Northwind- and
Feld-shaped targets registered in pytest fixtures, asserting INV-1 to INV-5.

Acceptance (backlog row): "The test runs in make check and fails on any agent-actor decision row
or any Accrued Agent approver attribution."

## Built
- The journey and `tests/integration/review/conftest.py` (the backfill fixtures by name).

## Progress log
- 2026-10-29: written (S15 group B); run at the end review.
