---
id: TASK-8005
title: "C-01-T05: closes contract stub PR 2 — intake, accounts, reconciliation, review, flux, portal"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: todo
branch: c01-t05-closes-stub-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T05
---

## Objective
closes contract stub PR 2 — intake, accounts, reconciliation, review, flux, portal.

## Plan
1. [ ] VMs: RequestTree, Questionnaire, CloseSummaryCard, AccountTree, Register, Workpaper, Arrangement, Reconciliation, ReconcilingItem, EntryDraft, IssueFacets, FluxSet, AnalyticLine, PortalQuestion.
2. [ ] 501 routes (epic §4.3) for intake, accounts, arrangements, reconciliations, entries, issues, transaction questions, flux, portal questions; refusal codes in `error-codes.yaml`.
3. [ ] `docs/contracts/closes.md` part 2.
Rollback: revert; flag-gated 501s.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
