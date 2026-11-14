---
id: TASK-7950
title: "F-07-T21: consumer contract tests for the tier-4 view models (C6, C4, C11, C21) and contract-request drafts"
plan_key: F-07-T21
spec: SPEC-652  # F-07 §4.5
acceptance_criteria: [AC-6]  # assertions run in each provider's CI; three contract requests list states and seed figures
risk_zone: green
status: in-review
branch: f07-t21-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Plan
- `backend/tests/contracts/f07_tier4/test_f07_tier4_consumers.py` (the contracts shard runs it in
  the providers' CI).
- `docs/contracts/requests/{t08-deadlines,t08-relationships,t06-form-pages}.md`.

## Partial
- The contract requests are committed documents, not GitHub issues (no issue is opened on the
  repository from this session).

## Progress log
- 2026-11-14: written, not run (S43 end pass).
