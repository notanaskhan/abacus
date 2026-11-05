---
id: TASK-3313
title: N-04-T18 eval suite for notices.responder with frozen thresholds
spec: SPEC-000  # row (N-04-T18)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T18
branch: s28-n04-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The suite is registered in _eval_suites.py with thresholds frozen by N's approval and its fake run is green in CI."

## Plan
- `evals/notices_responder/suite.yaml`: 40 CP2000 variants, 8 adversarial, 12 unmapped notices, 6 consent cases; thresholds per N-04 §6.
- `abacus_tools/evals/notices_responder.py` graders; `__main__` dispatch.
- `_eval_suites.py` regenerates once the spec exists (N-04-T19).
- Tests: negative controls.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2312
