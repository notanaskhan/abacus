---
id: TASK-8732
title: "Q-05-T07: Override producer payloads and the draft-vs-final accuracy read"
spec: SPEC-711
acceptance_criteria: [AC-3, AC-4]
risk_zone: amber
status: in-review
branch: s51p-q05-t07-producers-accuracy
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T07
---

## Objective
Finish Q-05-T07 (TASK-8714): proposal.decided carries the projection's facts from its producer (agent key from the proposing run, outcome adopted/changed/rejected, source, decision time, decider), and ADM-11's accuracy (fields the agent drafted on the prior tax year's filed returns, how many a person changed by the final) is read and served.

## Plan (amber)
1. agents/events.ProposalDecided: optional agent_key, outcome, source_id, decided_at, decided_by; agents/proposals._outcome_fields fills them from the proposal's run (approved→adopted, approved_with_edits→changed, rejected→rejected).
2. review/field_values.draft_accuracy (first value agent_suggested; final differs) exported from review api; tax/worksheet_review.filed_return_worksheets exported from tax api.
3. practice/quality_dashboard.accuracy; dashboard tile; GET /v1/quality/accuracy live.
4. tests/unit/practice/test_q05t07_producer_payload.py.

## Progress log
- `2026-11-19` — Built. Not built: the office narrowing of accuracy (returns carry no office; the read is firm-wide and the route says so), checkpoint and review-decision producers (a checkpoint that follows a proposal would count twice; they stay skipped until their owners add a distinct agent output), and the W7 back-fill equality check against pilot_metric_snapshots (needs the pilot metrics run). Gates and tests run once at the S51 end pass (build first, test last).
