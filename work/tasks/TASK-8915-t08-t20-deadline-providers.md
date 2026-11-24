---
id: TASK-8915
title: "T-08-T20: Filing-deadline providers registered; HOME-01 pane on filing_deadlines"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T20
---

## Objective
Row: "Filing-deadline providers in tax (returns, extension_for, installments_due, 706, 4768, 8971, 65-day window, 990), closes, notices and assurance (5500, report targets) registered to the slot; HOME-01 Your deadlines pane switches to filing_deadlines." Acceptance: "HOME-01 and HOME-03 show the same dates for Daniel Reyes, and the Thornbury 706 reads Nov 2, 2026 with Form 4768 to May 3, 2027."

## Done
- tax/deadline_sources.py: tax_return (incl. 706 via the estate due chip and 990), extension, estimate_batch, fiduciary_statement (8971), election_window (65-day)
- closes/, notices/, assurance/deadline_sources.py: close, notice_response, form_5500, assurance_report
- registered from each module's api; all eleven source kinds now registered
- practice recompute over every registered kind (window -400/+548 days), inputs_hash per fact, failing source isolated
- HOME-01 pane reads filing_deadlines rows (viewer as owner or signer) behind practice.filing_deadlines; DeadlineRowOut.deadline_id additive
- docs/contracts/filing-deadlines.md providers table; DEC-5917
- tests: tests/unit/practice/test_t08t20_deadline_providers.py (6 pass), tests/integration/test_t08t20_deadline_providers.py (end pass)

## Progress log
- `2026-11-23` — Built in full. End pass: integration tests (this row's and T-08-T10's recompute test), make generate for DeadlineRowOut.deadline_id.
