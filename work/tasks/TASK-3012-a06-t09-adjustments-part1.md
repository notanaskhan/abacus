---
id: TASK-3012
title: A-06-T09 adjustments service part 1 — propose, balance, thresholds, adjusted TB
spec: SPEC-642
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T09
branch: s25-a06-t09 (stacked on s25-a04-t24)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"An attest-client entry is always review_required, adjusted_tb(final) equals the snapshot plus
approved entries with debits equal to credits per layer, and nothing is ever stored as a layer."

## Plan (red)
- `adjustments/entries.py`: propose, entries_of, entry, recorded_entries (the ledger's source),
  adjusted_tb, audit owners.
- `methodology.api.aje_classification_for`.
- `adjustments/contract.py`: list, propose and adjusted TB served; `AdjustedLineOut.unadjusted` signed.
- No migration (0643). Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Balance rule; layers' source; no stored layer | `tests/unit/adjustments/test_a06t09_entries.py` |
| Attest always review required | 0643's CHECK; the service sets it |

## Progress log
- 2026-11-02: built. Security review of the red diff at the S25 end review.

## Decisions made during this task
DEC-2061.
