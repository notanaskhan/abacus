---
id: TASK-1734
title: Q-04-T013 Independent AC tests for the metric reads and the go-live check
spec: SPEC-403
acceptance_criteria: [AC-11]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T013
branch: s14-q04-t013
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 tests for Q-04-T006 (c06) and Q-04-T009 (c09). Acceptance (backlog row): "Tests prove the
allowlist, tenant isolation of the reads and a failing go-live item for each chapter 06 section
8.3 category."

## Plan (amber, tests only)
- `backend/tests/integration/test_q04t013_metrics_independent.py`: allowlist, isolation, shape.
- `backend/tests/unit/tools/test_q04t013_go_live_independent.py`: one failing item per category,
  manual dossier items. DEC-824.

## Progress log
- `2026-10-28` — Written. ruff and pyright clean. Not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** Q-04-T008.
