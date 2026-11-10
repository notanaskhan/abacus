---
id: TASK-6001
title: "N-04-T27 Notices release: contract frozen, RB-61, load profile, hand-offs"
spec: SPEC-000  # row (N-04-T27)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T27
branch: s29l-n04-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Notices are live at every pilot firm by Fri Dec 10, 2027 with at least one real notice, and no N-04 flag remains in the Jan 1-Apr 20 window.

## Plan
Freeze C-notices v1: `abacus_tools/contracts.py` MODELS gains `notices` (every route model of notices/contract.py), snapshot tests/contracts/notices/v1.json; the contract doc and NOT-01..03 screen contracts read final. Module README release section. RB-61 (hand-off to a person at the agency, missed follow-up, escalation, OCR or agent off, re-sent envelope, onboarding a firm's open notices, the Dec 7 flip and rollback) and the runbooks index row; RB-16 R4-15. Load profile `notices_desk` (list and summary; intake read and upload written down as not yet carried). Hand-off notes docs/plan/status/N-04-handoff.md for W-03, T-08, R-03, N-03. Flag retirement in its own held PR (DEC-2602). Rollback: revert; the snapshot only adds a check.

## Progress log
- 2026-11-07: built. Contract check (`python -m abacus_tools.contracts`) passes with the new snapshot; the profile loads. tests/contracts/test_frozen_snapshots.py runs the check at the end pass. Not done: onboarding real firms' open notices (none, DEC-1391), the Dec 7 flip approvals, pen test #2 (DEC-1389), the December load test itself (staging).

## Decisions made during this task
DEC-2601
