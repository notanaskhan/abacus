---
id: TASK-8535
title: "C-01-T39: CLS-06 Review states a-g"
spec: SPEC-655
acceptance_criteria: []
risk_zone: green
status: in-review
branch: c01-t39-cls06
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T39
---

## Objective
CLS-06 Review states a, a2, b, c, d, e, f, g on T9 close-review: severity-band queue with Exceptions and Notes; show resolved; issue detail with Why This Was Surfaced; register scroll-to-row and inline rec; resolve dialog with required note and optional Propose AJE; Not applicable; reopen; assignee picker including the client contact; Ask client. AC: the Review badge equals the open exceptions (2 + 5), Resolve stays disabled without a note, an issue assigned to the agent shows no resolve control for the agent.

## Plan (green)
1. fixtures/seed/close-review.ts: queue per state (d resolves Sound Electric, f adds the resolved Shopify duplicate, g empty), issue detail, notes, client answer, the handoff's 4410 August register (also CLS-05 f); scenarios/CLS-06.ts
2. screens/CLS-06: copy, index (CLS06 on closeIssuesOptions, closeRegisterOptions, closeReconciliationOptions; Resolve gated by the issue.resolve grant; Dialog with a required note), CLS-06.test.tsx; kit-close-data re-exports
3. routes/firm/closes.tsx: the Review tab body; Flux picker to CLS-10

## Progress log
- `2026-11-17` — Built; CLS-04/05/06 vitest 46 pass, tsc and eslint clean. The queue's detail beyond the list row (assignee, linked entities, client question) is fixture-only: C-01's issue contract carries no detail read yet, so the live swap (C-01-T43) needs a detail endpoint or the fields on CloseIssueOut. Ask client to POR-04 and Open thread (INB-04, N-03) wire in the live swap. Gates and tests run once at the S49 end pass (build first, test last).
