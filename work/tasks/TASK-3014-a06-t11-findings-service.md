---
id: TASK-3014
title: A-06-T11 findings service
spec: SPEC-642
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T11
branch: s25-a06-t11 (stacked on s25-a06-t10)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"The Northwind list returns bands 1 + 2 + 1 + 5 = 9 with badge 3, an uncited agent finding is
refused, and resolve or not-applicable by an agent principal is denied."

## Built
- `assurance/findings.py`; `findings_contract.py` routes served, new not-applicable route; `review.api`
  exports `move_issue`, `issue_row`; `make generate`.

## Acceptance
| Check | Test |
|---|---|
| Bands foot; badge 3 | `tests/unit/assurance/test_a06t11_findings.py` |
| Uncited agent finding refused | same |
| Agent denied resolve and not applicable | same (matrix) |

## Progress log
- 2026-11-02: built. Partial: the issue and the finding are two units of work; projected
  conversion waits for A-03's projection facts (DEC-2063).

## Decisions made during this task
DEC-2063.
