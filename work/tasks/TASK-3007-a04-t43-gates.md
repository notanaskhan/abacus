---
id: TASK-3007
title: A-04-T43 assurance/gates.py with the G4 provider
spec: SPEC-620
acceptance_criteria: [AC-22]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T43
branch: s25-a04-t43 (stacked on s25-a04-t18)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Northwind's G4 reads met after the 4:40 PM decision and reopens with
register_changed_after_approval after an edit to R4, and an amber PR cannot change gates.py."

## Plan (red)
- `assurance/gates.py`: `register()` → `register_gate_provider("G4", g4_facts)`; called from
  `assurance/api.py`.
- `protected-paths.md`: gates.py named red.
- `test_preregistration.py`: the unregistered-gate example unregisters G4 itself.
- Rollback: revert (G4 reads `no_gate_provider` again).

## Acceptance
| Check | Test |
|---|---|
| G4 registered from gates.py over g4_facts | `tests/unit/assurance/test_a04t43_gates.py` |
| Met / reopened facts | A-04-T18's `test_ac4_4_*` |

## Progress log
- 2026-11-02: built. Tests at the S25 end review.

## Decisions made during this task
DEC-2057.
