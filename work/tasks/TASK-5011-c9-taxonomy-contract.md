---
id: TASK-5011
title: "C9 taxonomy half: document the live mapping operations"
spec: SPEC-316
acceptance_criteria: [AC-8, AC-9]
risk_zone: green
status: done
branch: task-5011-c9-mapping-contract
worktree: agentwt
created: 2026-10-30
updated: 2026-10-30
---

## Plan keys
A-03-T03 (partial: the contract text for what's live; the v2 stub and freeze are still to come).

## Plan
- `docs/contracts/c09-ledger.md` gains a "Taxonomy half, live v0" section covering callers, mapping order, human-only actions, errors, audit and outbox events, and what C9 v2 adds.
- **Rollback:** revert the PR.

## Progress log
- Docs only. check-fast passes.

## Definition of done
- [x] check-fast passes.
