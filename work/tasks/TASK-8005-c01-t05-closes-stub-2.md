---
id: TASK-8005
title: "C-01-T05: closes contract stub PR 2 — intake, accounts, reconciliation, review, flux, portal"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: c01-t05-closes-stub-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T05
---

## Objective
closes contract stub PR 2 — intake, accounts, reconciliation, review, flux, portal.

## Plan
1. [x] VMs: RequestTree, Questionnaire, CloseSummaryCard, AccountTree, Register, Workpaper, Arrangement, Reconciliation, ReconcilingItem, EntryDraft, IssueFacets, FluxSet, AnalyticLine, PortalQuestion.
2. [x] 501 routes (epic §4.3) for intake, accounts, arrangements, reconciliations, entries, issues, transaction questions, flux, portal questions; refusal codes in `error-codes.yaml`.
3. [x] `docs/contracts/closes.md` part 2.
Rollback: revert; flag-gated 501s.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: `closes/contract_work.py`, 24 routes (CLS-03 tree, questionnaire, intake summary; CLS-04 accounts, register, workpaper and xlsx, arrangements, recategorization; CLS-05 reconciliation, resolve, entry draft, propose entry; CLS-06 issues, transaction questions; CLS-10 flux, xlsx, explain, edit, accept; POR-11 portal questions and answer). Portal routes answer only client principals behind `closes.portal_requests`; the portal DTO carries client wording and context only (QC-9). Refusal codes `open_items`, `statement_not_available`, `question_template_required`. Contract doc §4–§10; route introspection and error codes regenerated. Part 1's pyright cleanups (list defaults) ride along.
- **Partial.** 501 stubs; the FE builds the six screens on fixture handlers (T12 and each screen row), not on seed-backed routes (figure book T13). The existing C3 and C5 consumer suites are untouched (no change to their modules) and run at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
