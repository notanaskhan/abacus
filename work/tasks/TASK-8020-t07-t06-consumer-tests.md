---
id: TASK-8020
title: "T-07-T06: consumer contract tests for the contracts T-07 consumes in new ways"
spec: SPEC-656
acceptance_criteria: [AC-15]
risk_zone: amber
status: in-review
branch: t07-t06-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-07-T06
---

## Objective
consumer contract tests for the contracts T-07 consumes in new ways.

## Plan
Files: `tests/contracts/fiduciary/test_t07_consumers.py`: C4 `instrument_clause` registration shape (ADR-343 locator), C7 `form_8879_f` purpose and completion event, C10 1041 release registry entry, C17 tax tool registration shape, C19 consent predicate on a trust taxpayer, C21 fiduciary rule kinds; plus the stub route inventory and the typed fixtures' footing.

## Progress log
- `2026-11-14` — Built `tests/contracts/fiduciary/test_t07_consumers.py`: C4 (`document_text`, ADR-343 locator keys), C7 (`form_8879_f` in Purpose and EFILE_PURPOSES), C10 (`1041` in the K-1 forms), C17 (AgentTool fields, read/propose kinds, `tri`, `consent_required`), C19 (`consent_7216` reason), C21 (706 Nov 2, 2026 and 4768 May 3, 2027; 1041 7004 Sep 30), FW-1/EW-1 route inventory, no clause text, footing fixtures. ruff and pyright clean; run at the end pass.
- **Partial.** The `instrument_clause` kind assertion joins this file with T-07-T11 (the kind registers there); C21's 65-day and Form 8971 "earlier of" rule kinds do not exist in K-02's engine yet (T-07 §4.1 practice row: T09/T22 add them), so only the 706, 4768 and 1041 rules are pinned.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
