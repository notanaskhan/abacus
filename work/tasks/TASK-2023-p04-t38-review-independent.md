---
id: TASK-2023
title: P-04-T38 Independent AC tests for issues, checkpoints and field history
spec: SPEC-360
acceptance_criteria: [AC-10]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T38
branch: s15n-p04-t38
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Independent tests (ADR-078): restore never deletes, an import checkpoint stays pending until a
person approves, client wording never carries the internal note, field writes only through
`record_value`.

Acceptance (backlog row): "Tests written in ayushkbhatia's session pass and fail if a direct
cell write bypasses record_value."

## Tests
- `backend/tests/unit/review/test_p04t38_field_writes_only_through_record_value.py`
- `backend/tests/integration/backfill/test_p04t38_review_independent.py`

## Progress log
- 2026-10-29: written (S15 group B); run at the end review.
