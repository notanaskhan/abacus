---
id: TASK-3018
title: P-04-T59 review hardening
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T59
branch: s25-p04-t59 (stacked on s25-p04-t60)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"backend/mutation-thresholds.yaml records the review floor, the p95 budgets hold under the x25
load profile, and every review table registers its retention record type."

## Built
- Mutation scope `review` and its floor (0, target 75; DEC-2065).
- `evidence.retention.RECORD_TYPES` += `review_record`; `review.registry.RETENTION_RECORD_TYPES`.
- `review.slots.register_archive_lock`, checked in `record_sign_off` and `decide_card`.
- Load profile `review_grammar.yaml` (x25, p95 500 ms reads); SLO-14 in `docs/ops/slos.md`.

## Progress log
- 2026-11-02: built. Partial: the floor's 75 waits for the first weekly baseline; the write budgets
  wait for the fleet's review ids; the alarm waits for the observability module (DEC-2065).

## Decisions made during this task
DEC-2065.
